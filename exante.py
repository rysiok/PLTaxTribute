import csv
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
import click

import requests
import simplejson as json
from tabulate import tabulate


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class TransactionSide(Enum):
    BUY = 1
    SELL = 2


class CashFlowItemType(Enum):
    COMMISSION = 1
    TRADE = 2
    PL = 3


# exante transaction log column positions
class Column:
    ID = 0
    SYMBOL = 2
    ISIN = 3
    OP_TYPE = 4
    TIME = 5
    SUM = 6
    ASSET = 7
    COMMENT = 10


class TradeTransaction:
    def __init__(self, time: datetime, side: TransactionSide, price: Decimal, currency: str, count: int, commission: Decimal, symbol: str):
        self.time = time
        self.side = side
        self.price = price
        self.currency = currency
        self.count = count
        self.commission = commission
        self.symbol = symbol


class CashFlowItem:
    def __init__(self, type: CashFlowItemType, time: datetime, count: int, price: Decimal, currency: str, pln: Decimal):
        self.type = type
        self.time = time
        self.count = count
        self.price = price
        self.currency = currency
        self.pln = pln

    def __repr__(self):
        return repr((
            self.type.name,
            self.time,
            self.count,
            self.price,
            self.currency,
            self.pln
        ))


class NBP:
    cache = {}

    def __init__(self, cache_file: str = ".cache"):
        self.cache_file = cache_file

    def save_cache(self):
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self.cache, f)
        except OSError:
            pass

    def load_cache(self):
        try:
            with open(self.cache_file, "rb") as f:
                self.cache = {k: round(Decimal(v), 4) for k, v in json.load(f).items()}
        except OSError:
            pass

    def get_nbp_day_before(self, currency: str, date: datetime):
        date = date.date()
        exchange_date = date - timedelta(days=1)

        hash = f"{date} {currency}"

        hit = self.cache.get(hash, None)
        if hit:
            return hit

        while True:
            response = requests.get(r"https://api.nbp.pl/api/exchangerates/rates/a/%s/%s?format=json" % (currency, exchange_date))
            if response.status_code == 200:
                data = round(Decimal(response.json()["rates"][0]["mid"]), 4)
                self.cache[hash] = data
                return data
            exchange_date = exchange_date - timedelta(days=1)


class Transaction:
    @staticmethod
    def parse(csv_rows: list):
        op_type = csv_rows[0][Column.OP_TYPE]
        if op_type == "TRADE":
            time = datetime.fromisoformat(csv_rows[0][Column.TIME])
            count = int(csv_rows[0][Column.SUM])
            side = TransactionSide.BUY if count > 0 else TransactionSide.SELL
            price = abs(Decimal(csv_rows[1][Column.SUM]) / count)
            count = abs(count)
            commission = abs(Decimal(csv_rows[2][Column.SUM]))
            currency = csv_rows[1][Column.ASSET]
            symbol = csv_rows[0][Column.ASSET]

            return TradeTransaction(time, side, price, currency, count, commission, symbol)
        if op_type == "FUNDING/WITHDRAWAL":
            return None

        print(bcolors.WARNING + "Unsupported transaction type. Only TRADE are supported.")
        print(f"{op_type}{bcolors.ENDC}")
        return None


class Account:
    def __init__(self):
        self.cashflows = {}
        self.transaction_log = {}

    def load_transaction_log(self, file):
        rows = []
        with open(file, newline='', encoding="utf-16") as csvfile:
            reader = csv.reader(csvfile, delimiter='\t')
            next(reader, None)  # skip header
            rows = [row for row in reader]
        rows.sort(key=lambda i: i[Column.ID])
        group_by_time_log = {}
        for row in rows:  # group transaction by time
            time = datetime.fromisoformat(row[Column.TIME])
            # TODO: implement group by year
            if time.date().year != 2020:
                continue
            group_by_time_log[time] = [row] if time not in group_by_time_log.keys() else group_by_time_log[time] + [row]

        for v in group_by_time_log.values():  # parse rows groupped by time
            transaction_log_item = Transaction.parse(v)
            if transaction_log_item:
                s = transaction_log_item.symbol
                self.transaction_log[s] = [transaction_log_item] if s not in self.transaction_log.keys() else self.transaction_log[s] + [transaction_log_item]

    def init_cash_flow(self, nbp=NBP()):
        nbp.load_cache()

        for symbol, tr in self.transaction_log.items():
            sell = [t for t in tr if t.side == TransactionSide.SELL]
            buy = [t for t in tr if t.side == TransactionSide.BUY]

            if not buy:
                print(f"{bcolors.WARNING}No BUY transactions for symbol: {symbol}.{bcolors.ENDC}")
                continue

            cashflow = []
            for s in sell:
                pln = nbp.get_nbp_day_before(s.currency, s.time)
                cashflow.append(CashFlowItem(CashFlowItemType.TRADE, s.time, s.count, s.price, s.currency, pln))
                cashflow.append(CashFlowItem(CashFlowItemType.COMMISSION, s.time, -1, s.commission, s.currency, pln))

                while s.count and buy:
                    b = buy[0]
                    b.count -= s.count
                    pln = nbp.get_nbp_day_before(s.currency, b.time)
                    if b.count <= 0:
                        cashflow.append(CashFlowItem(CashFlowItemType.TRADE, b.time, -(b.count + s.count), b.price, s.currency, pln))
                        cashflow.append(CashFlowItem(CashFlowItemType.COMMISSION, b.time, -1, b.commission, s.currency, pln))  # full cost
                        s.count = -b.count  # left count
                        del buy[0]
                    else:
                        cashflow.append(CashFlowItem(CashFlowItemType.TRADE, b.time, -s.count, b.price, s.currency, pln))
                        ratio = Decimal(s.count / (s.count + b.count))
                        commission = round(b.commission * ratio, 2)
                        cashflow.append(CashFlowItem(CashFlowItemType.COMMISSION, b.time, -1, commission, s.currency,
                                                     nbp.get_nbp_day_before(s.currency, s.time)))  # partial cost
                        b.commission -= commission
                        break
            self.cashflows[symbol] = cashflow

        nbp.save_cache()

    def get_foreign(self):
        table = [["symbol", "currency", "income", "cost", "P/L", "(commission)"]]
        for symbol, cashflow in self.cashflows.items():
            trade_income = sum([cf.count * cf.price for cf in cashflow if cf.count > 0 and cf.type == CashFlowItemType.TRADE])
            trade_cost = -sum([cf.count * cf.price for cf in cashflow if cf.count < 0 and cf.type == CashFlowItemType.TRADE])
            commission_cost = -sum([cf.count * cf.price for cf in cashflow if cf.type == CashFlowItemType.COMMISSION])
            assert sum([cf.count * cf.price for cf in cashflow if cf.count > 0 and cf.type == CashFlowItemType.COMMISSION]) == 0, f"commission_cost != 0"

            if cashflow:  # output only items with data
                table.append(
                    [symbol, cashflow[0].currency, trade_income, trade_cost + commission_cost, trade_income - trade_cost - commission_cost, commission_cost])
        return table

    def get_pln(self):
        table = [["symbol", "income", "cost", "P/L", "(commission)"]]
        total_trade_income = 0
        total_trade_cost = 0

        for symbol, cashflow in self.cashflows.items():
            trade_income = sum([round(cf.count * cf.price * cf.pln, 2) for cf in cashflow if cf.count > 0 and cf.type == CashFlowItemType.TRADE])
            trade_cost = -sum([round(cf.count * cf.price * cf.pln, 2) for cf in cashflow if cf.count < 0 and cf.type == CashFlowItemType.TRADE])
            commission_cost = -sum([round(cf.count * cf.price * cf.pln, 2) for cf in cashflow if cf.type == CashFlowItemType.COMMISSION])

            if cashflow:  # output only items with data
                table.append([symbol, trade_income, trade_cost + commission_cost, trade_income - trade_cost - commission_cost, commission_cost])
                total_trade_income += trade_income
                total_trade_cost += trade_cost + commission_cost

        table.append(["-----"])
        table.append(["TOTAL", total_trade_income, total_trade_cost, total_trade_income - total_trade_cost])
        return table

    def get_pln_total(self):
        table = [["income", "cost", "P/L"]]
        trade_income = sum([round(cf.count * cf.price * cf.pln, 2) for key in self.cashflows for cf in self.cashflows[key] if
                            cf.count > 0 and cf.type == CashFlowItemType.TRADE])
        trade_cost = -sum([round(cf.count * cf.price * cf.pln, 2) for key in self.cashflows for cf in self.cashflows[key] if cf.count < 0])
        table.append([trade_income, trade_cost, trade_income - trade_cost])
        return table


def ls(text: str):
    text = text.strip() + " "
    print()
    print("* " + text + "*" * (10 - len(text)))


@click.group(chain=True)
@click.option('-i', '--input-file', required=True, help='Transaction log file name.')
@click.pass_context
# @click.option('--output', type=click.Choice(['TABLE', 'JSON'], case_sensitive=False), default='TABLE', help='Transaction log file name.')
def cli(ctx, input_file):
    """This script Calculates income and cost from Exante transaction log, using FIFO approach and D-1 NBP PLN exchange rate."""
    account = Account()
    account.load_transaction_log(input_file)
    account.init_cash_flow()
    ctx.obj["account"] = account


@cli.command(help='Calculation without conversion to PLN per asset.')
@click.pass_context
def foreign(ctx):
    account = ctx.obj['account']
    ls("FOREIGN")
    print(tabulate(account.get_foreign(), headers="firstrow", floatfmt=".2f", tablefmt="presto"))


@cli.command(help='Calculation in PLN per asset (includes total).')
@click.pass_context
def pln(ctx):
    account = ctx.obj['account']
    ls("PLN")
    print(tabulate(account.get_pln(), headers="firstrow", floatfmt=".2f", tablefmt="presto"))


@cli.command(help='Total calculation in PLN.')
@click.pass_context
def total(ctx):
    account = ctx.obj['account']
    ls("TOTAL")
    print(tabulate(account.get_pln_total(), headers="firstrow", floatfmt=".2f", tablefmt="presto"))


if __name__ == '__main__':
    cli(obj={})
