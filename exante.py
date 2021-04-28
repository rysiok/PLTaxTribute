import csv
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import List

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
    DIVIDEND = 3


class CashFlowItemType(Enum):
    COMMISSION = 1
    TRADE = 2
    PL = 3
    DIVIDEND = 4
    TAX = 5


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


# Mintos transaction log column positions
class MintosColumn:
    TIME = 0
    DETAILS = 2
    TURNOVER = 3
    CURRENCY = 5


class Transaction:
    def __init__(self, time: datetime, side: TransactionSide, symbol: str):
        self.time = time
        self.side = side
        self.symbol = symbol

    @staticmethod
    def parse(row: List[str], log: dict):
        op_type = row[Column.OP_TYPE]
        supported_op_types = ("TRADE", "COMMISSION", "DIVIDEND", "TAX")

        if op_type == "FUNDING/WITHDRAWAL":
            return

        if op_type not in supported_op_types:
            print(f"{bcolors.WARNING}Unsupported transaction type {op_type}.{bcolors.ENDC}")
            return

        time = datetime.fromisoformat(row[Column.TIME])
        isin = row[Column.ISIN]
        asset = row[Column.ASSET]
        symbol = row[Column.SYMBOL]

        # count, side for TradeTransaction
        if op_type == "TRADE" and isin != "None" and asset == symbol:
            count = int(row[Column.SUM])
            side = TransactionSide.BUY if count > 0 else TransactionSide.SELL
            count = abs(count)
            log_item = TradeTransaction(time=time, side=side, count=count, symbol=symbol)
            log[symbol] = [log_item] if symbol not in log.keys() else log[symbol] + [log_item]
            return

        if op_type == "DIVIDEND":
            value = Decimal(row[Column.SUM])
            log_item = DividendTransaction(time=time, value=value, symbol=symbol, currency=asset)
            log[symbol] = [log_item] if symbol not in log.keys() else log[symbol] + [log_item]
            return

        # another row of transaction object
        last_log_item = log[symbol][-1]

        if isin == "None" and last_log_item.time == time and last_log_item.symbol == symbol:
            # price, currency for last TradeTransaction
            if op_type == "TRADE":
                last_log_item.price = abs(Decimal(row[Column.SUM]) / last_log_item.count)
                last_log_item.currency = asset
                return
            # commission for last TradeTransaction
            if op_type == "COMMISSION":
                last_log_item.commission = abs(Decimal(row[Column.SUM]))
                return
        # tax for DividendTransaction
        if op_type == "TAX":
            last_log_item.tax = abs(Decimal(row[Column.SUM]))
            return

    @staticmethod
    def parseMintos(row: List[str], log: dict):
        if len(row) == 1:  # skip invalid entries
            return
        details = row[MintosColumn.DETAILS].lower()

        include = ("interest received",
                   #"late fees received",
                   "secondary market fee",
                   #"discount/premium for secondary market transaction",
                   )

        if all([i not in details for i in include]):
            return


        time = datetime.fromisoformat(row[MintosColumn.TIME])
        value = Decimal(row[MintosColumn.TURNOVER])
        currency = row[MintosColumn.CURRENCY]
        symbol = "M"
        log_item = DividendTransaction(time=time, value=value, symbol=symbol, currency=currency)
        log[symbol] = [log_item] if symbol not in log.keys() else log[symbol] + [log_item]


class TradeTransaction(Transaction):
    def __init__(self, time: datetime, side: TransactionSide, symbol: str, count: int, price: Decimal = None, currency: str = None, commission: Decimal = None):
        super().__init__(time, side, symbol)
        self.price = price
        self.currency = currency
        self.count = count
        self.commission = commission


class DividendTransaction(Transaction):
    def __init__(self, time: datetime, symbol: str, value: Decimal, currency: str, tax: Decimal = None):
        super().__init__(time, TransactionSide.DIVIDEND, symbol)
        self.value = value
        self.tax = tax
        self.currency = currency


class CashFlowItem:
    def __init__(self, type: CashFlowItemType, time: datetime, count: int, price: Decimal, currency: str, pln: Decimal):
        self.type = type
        self.time = time
        self.count = count
        self.price = price
        self.currency = currency
        self.pln = pln


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


class Account:
    """
1. Load transaction log into an array from CSV file and sort it ascending by transaction id.
2. For each transaction check operation type. Based on it create TradeTransaction or DividendTransaction.
   Fill missing data (ie. price, commission, tax) based on data in following transactions.
   Store Transactions list in dictionary using symbol as a key (group Transaction by symbol)
3. For each symbol process sell Transactions and create CashFlowItem (TRADE, COMMISSION, DIVIDEND, TAX), based on FIFO method, getting amount in PLN based D-1 exchange rate,
   where transaction time is T+0.  Store each CashFlowItem list in a dictionary using symbol as a key.

    During sum calculations Use round(2) on CashFlowItem level after multiplication count * price * pln exchange rate before sum. Decimal is used for floating pont calculations.

    """

    def __init__(self):
        self.cashflows = {}
        self.transaction_log = {}

    def load_transaction_log(self, file):
        with open(file, newline='', encoding="utf-16") as csvfile:
            reader = csv.reader(csvfile, delimiter='\t')
            next(reader, None)  # skip header
            rows = [row for row in reader]
        rows.sort(key=lambda i: i[Column.ID])
        for row in rows:
            Transaction.parse(row, self.transaction_log)

    def load_mintos_transaction_log(self, file):
        with open(file, newline='') as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            next(reader, None)  # skip header
            rows = [row for row in reader]
        rows.sort(key=lambda i: i[MintosColumn.TIME])
        for row in rows:
            Transaction.parseMintos(row, self.transaction_log)

    def init_cash_flow(self, nbp=NBP()):
        nbp.load_cache()

        for symbol, tr in self.transaction_log.items():
            sell = [t for t in tr if t.side == TransactionSide.SELL]
            buy = [t for t in tr if t.side == TransactionSide.BUY]
            dividend = [t for t in tr if t.side == TransactionSide.DIVIDEND]

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
                    if b.count <= 0:  # more to sell or everything sold
                        cashflow.append(CashFlowItem(CashFlowItemType.TRADE, b.time, -(b.count + s.count), b.price, s.currency, pln))
                        cashflow.append(CashFlowItem(CashFlowItemType.COMMISSION, b.time, -1, b.commission, s.currency, pln))  # full cost
                        s.count = -b.count  # left count
                        del buy[0]  # remove matching buy transaction
                    else:  # partial sell
                        cashflow.append(CashFlowItem(CashFlowItemType.TRADE, b.time, -s.count, b.price, s.currency, pln))
                        ratio = Decimal(s.count / (s.count + b.count))
                        commission = round(b.commission * ratio, 2)
                        cashflow.append(CashFlowItem(CashFlowItemType.COMMISSION, b.time, -1, commission, s.currency,
                                                     nbp.get_nbp_day_before(s.currency, s.time)))  # partial cost
                        b.commission -= commission
                        break
            for d in dividend:
                pln = nbp.get_nbp_day_before(d.currency, d.time)
                cashflow.append(CashFlowItem(CashFlowItemType.DIVIDEND, d.time, 1, d.value, d.currency, pln))
                cashflow.append(CashFlowItem(CashFlowItemType.TAX, d.time, 1, d.tax, d.currency, pln))

            self.cashflows[symbol] = cashflow

        nbp.save_cache()

    def init_mintos_cash_flow(self, nbp=NBP()):
        nbp.load_cache()

        for symbol, tr in self.transaction_log.items():
            dividend = [t for t in tr if t.side == TransactionSide.DIVIDEND]
            cashflow = []
            for d in dividend:
                pln = nbp.get_nbp_day_before(d.currency, d.time)
                cashflow.append(CashFlowItem(CashFlowItemType.DIVIDEND, d.time, 1, d.value, d.currency, pln))

            self.cashflows[symbol] = cashflow

        nbp.save_cache()

    def get_foreign(self):
        table = [["symbol", "currency", "income", "cost", "P/L", "(commission)"]]
        for symbol, cashflow in self.cashflows.items():
            if cashflow:  # output only items with data
                trade_income = sum([cf.count * cf.price for cf in cashflow if cf.count > 0 and cf.type == CashFlowItemType.TRADE])
                if trade_income:
                    trade_cost = -sum([cf.count * cf.price for cf in cashflow if cf.count < 0 and cf.type == CashFlowItemType.TRADE])
                    commission_cost = -sum([cf.count * cf.price for cf in cashflow if cf.type == CashFlowItemType.COMMISSION])
                    assert sum([cf.count * cf.price for cf in cashflow if cf.count > 0 and cf.type == CashFlowItemType.COMMISSION]) == 0, f"commission_cost != 0"

                    table.append(
                        [symbol, cashflow[0].currency, trade_income, trade_cost + commission_cost, trade_income - trade_cost - commission_cost, commission_cost])
        return table

    def get_pln(self):
        table = [["symbol", "income", "cost", "P/L", "(commission)"]]
        total_trade_income = 0
        total_trade_cost = 0

        for symbol, cashflow in self.cashflows.items():
            if cashflow:  # output only items with data
                trade_income = sum([round(cf.count * cf.price * cf.pln, 2) for cf in cashflow if cf.count > 0 and cf.type == CashFlowItemType.TRADE])
                if trade_income:
                    trade_cost = -sum([round(cf.count * cf.price * cf.pln, 2) for cf in cashflow if cf.count < 0 and cf.type == CashFlowItemType.TRADE])
                    commission_cost = -sum([round(cf.count * cf.price * cf.pln, 2) for cf in cashflow if cf.type == CashFlowItemType.COMMISSION])

                    table.append([symbol, trade_income, trade_cost + commission_cost, trade_income - trade_cost - commission_cost, commission_cost])
                    total_trade_income += trade_income
                    total_trade_cost += trade_cost + commission_cost

        table.append(["-----"])
        table.append(["TOTAL", total_trade_income, total_trade_cost, total_trade_income - total_trade_cost])
        return table

    def get_pln_total(self):
        table = [["income\r[PIT38 C22]", "cost\r[PIT38 C23]", "P/L"]]
        trade_income = sum([round(cf.count * cf.price * cf.pln, 2) for key in self.cashflows for cf in self.cashflows[key] if
                            cf.count > 0 and cf.type == CashFlowItemType.TRADE])
        trade_cost = -sum([round(cf.count * cf.price * cf.pln, 2) for key in self.cashflows for cf in self.cashflows[key] if cf.count < 0])
        table.append([trade_income, trade_cost, trade_income - trade_cost])
        return table

    def get_dividends(self):
        table = [["symbol", "currency", "income", "paid tax", "%"]]
        for symbol, cashflow in self.cashflows.items():
            if cashflow:  # output only items with data
                income = sum([cf.price for cf in cashflow if cf.type == CashFlowItemType.DIVIDEND])
                tax = sum([cf.price for cf in cashflow if cf.type == CashFlowItemType.TAX])
                if income > 0:
                    percent = round(tax / income * 100)
                    table.append([symbol, cashflow[0].currency, income, tax, percent])
        return table

    def get_dividends_pln(self):
        table = [["income", "paid tax\r[PIT38 G45]", "%", "total to pay (19%)\r[PIT38 G46]", "left to pay (19%)\r[PIT38 G47]"]]
        income = sum([round(cf.count * cf.price * cf.pln, 2) for key in self.cashflows for cf in self.cashflows[key] if cf.type == CashFlowItemType.DIVIDEND])
        paid_tax = sum([round(cf.count * cf.price * cf.pln, 2) for key in self.cashflows for cf in self.cashflows[key] if cf.type == CashFlowItemType.TAX])
        if income > 0:
            percent = round(paid_tax / income * 100)
            tax = round(income * Decimal("0.19"), 2)
            left_to_pay = round(tax - paid_tax)
            table.append([income, paid_tax, percent, tax, left_to_pay])
        return table

    def get_mintos(self):
        table = [["symbol", "currency", "income"]]
        for symbol, cashflow in self.cashflows.items():
            if cashflow:  # output only items with data
                income = sum([cf.price for cf in cashflow if cf.type == CashFlowItemType.DIVIDEND])
                if income > 0:
                    table.append([symbol, cashflow[0].currency, income])
        return table

    def get_mintos_pln(self):
        table = [["income", "total to pay (19%)\r[PIT38 G46]", "left to pay (19%)\r[PIT38 G47]"]]
        income = sum([round(cf.count * cf.price * cf.pln, 2) for key in self.cashflows for cf in self.cashflows[key] if cf.type == CashFlowItemType.DIVIDEND])
        if income > 0:
            tax = round(income * Decimal("0.19"), 2)
            left_to_pay = round(tax)
            table.append([income, tax, left_to_pay])
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
    """This script calculates trade income, cost, dividends and paid tax from Exante transaction log, using FIFO approach and D-1 NBP PLN exchange rate."""
    account = Account()
    account.load_mintos_transaction_log(input_file)
    account.init_mintos_cash_flow()
    ctx.obj["account"] = account


@cli.command(help='Trade income/cost without conversion to PLN per asset.')
@click.pass_context
def foreign(ctx):
    account = ctx.obj['account']
    ls("FOREIGN")
    print(tabulate(account.get_foreign(), headers="firstrow", floatfmt=".2f", tablefmt="presto"))


@cli.command(help='Trade income/cost in PLN per asset (includes total).')
@click.pass_context
def pln(ctx):
    account = ctx.obj['account']
    ls("PLN")
    print(tabulate(account.get_pln(), headers="firstrow", floatfmt=".2f", tablefmt="presto"))


@cli.command(help='Total trade income/cost in PLN.')
@click.pass_context
def total(ctx):
    account = ctx.obj['account']
    ls("TOTAL PLN")
    print(tabulate(account.get_pln_total(), headers="firstrow", floatfmt=".2f", tablefmt="presto"))


@cli.command(help='Dividend and paid tax witohut conversion to PLN per asset.')
@click.pass_context
def dividend(ctx):
    account = ctx.obj['account']
    ls("FOREIGN DIVIDEND")
    print(tabulate(account.get_dividends(), headers="firstrow", floatfmt=".2f", tablefmt="presto"))


@cli.command(help='Mintos income in original currency.')
@click.pass_context
def mintos(ctx):
    account = ctx.obj['account']
    ls("MINTOS INCOME")
    print(tabulate(account.get_mintos(), headers="firstrow", floatfmt=".2f", tablefmt="presto"))


@cli.command(help='Mintos income in PLN.')
@click.pass_context
def mintos_pln(ctx):
    account = ctx.obj['account']
    ls("MINTOS INCOME PLN")
    print(tabulate(account.get_mintos_pln(), headers="firstrow", floatfmt=".2f", tablefmt="presto"))


@cli.command(help='Dividend and paid tax in PLN.')
@click.pass_context
def dividend_pln(ctx):
    """
        Kwotę należnego podatku wpisuje do pola o enigmatycznej nazwie „Zryczałtowany podatek obliczony od przychodów (dochodów), o których mowa w art. 30a ust. 1 pkt 1–5 ustawy, uzyskanych poza granicami Rzeczypospolitej Polskiej”.
        Kwotę podatku pobranego za granicą wpisujemy do pola „Podatek zapłacony za granicą, o którym mowa w art. 30a ust. 9 ustawy”.

        2019
        W PIT-36 – pola 355, 356, 357 i 358 w sekcji N.
        W PIT-36L – pola 115 i 116 w sekcji K.
        W PIT-38 – pola 45 i 46 w sekcji G.
    """
    account = ctx.obj['account']
    ls("PLN DIVIDEND")
    print(tabulate(account.get_dividends_pln(), headers="firstrow", floatfmt=".2f", tablefmt="presto"))


if __name__ == '__main__':
    cli(obj={})
