from tabulate import tabulate
import csv
import requests
import pickle
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum


# saves cache to file
def save_cache(filename, CACHE):
    try:
        with open(filename, "wb") as f:
            pickle.dump(CACHE, f)
    except OSError:
        pass


# loads cache from file
# unsafe, don't relay on external cache
def load_cache(filename):
    try:
        with open(filename, "rb") as f:
            return pickle.load(f)
    except OSError:
        return {}


class TransactionSide(Enum):
    BUY = 1
    SELL = 2


class CashFlowItemType(Enum):
    COMMISSION = 1
    TRADE = 2
    PL = 3


# exante transaction log column positions
class Column:
    TIME = 0
    SIDE = 2
    SYMBOL = 3
    PRICE = 6
    CURRENCY = 7
    COUNT = 8
    COMMISSION = 9
    VOLUME = 12


class Transaction:

    def __init__(self, time: datetime, side: TransactionSide, price: Decimal, currency: str, count: int, commission: Decimal, volume: Decimal):
        self.time = time
        self.side = side
        self.price = price
        self.currency = currency
        self.count = count
        self.commission = commission
        self.volume = volume

    @staticmethod
    def from_cvs_row(csv_row):
        return Transaction(datetime.fromisoformat(csv_row[Column.TIME]),
                           TransactionSide.BUY if csv_row[Column.SIDE] == "buy" else TransactionSide.SELL,
                           Decimal(csv_row[Column.PRICE]), row[Column.CURRENCY], int(csv_row[Column.COUNT]), Decimal(csv_row[Column.COMMISSION]),
                           Decimal(csv_row[Column.VOLUME])
                           )

    @staticmethod
    def get_symbol(csv_row):
        return csv_row[Column.SYMBOL]

    def __repr__(self):
        return repr((
            self.time,
            self.side.name,
            self.price,
            self.currency,
            self.count,
            self.commission,
            self.volume,
        ))


class CashFlowItem:
    def __init__(self, type: CashFlowItemType, time: datetime, count: int, price: Decimal, currency: str = "USD"):
        self.type = type
        self.time = time
        self.count = count
        self.price = price
        self.currency = currency

    def __repr__(self):
        return repr((
            self.type.name,
            self.time,
            self.count,
            self.price,
            self.currency,
        ))


def get_nbp_day_before(currency: str, date: datetime):
    date = date.date()
    exchange_date = date - timedelta(days=1)

    if 'NBP' not in CACHE:
        CACHE['NBP'] = {}
    if (currency, date) in CACHE['NBP']:
        return CACHE['NBP'][(currency, date)]

    while True:
        try:
            response = requests.get(r"https://api.nbp.pl/api/exchangerates/rates/a/%s/%s?format=json" % (currency, exchange_date))
            data = round(Decimal(response.json()["rates"][0]["mid"]), 4)
            CACHE['NBP'][(currency, date)] = data
            return data
        except:
            exchange_date = exchange_date - timedelta(days=1)


class Account:
    cashflows = {}

    def init_cash_flow(self, transaction_log):
        for symbol, tr in transaction_log.items():
            # tr.sort(key=lambda x: x.time)
            tr.reverse()

            sell = [t for t in tr if t.side == TransactionSide.SELL]
            buy = [t for t in tr if t.side == TransactionSide.BUY]

            cashflow = []
            if __debug__:
                pl = 0
            for s in sell:
                cashflow.append(CashFlowItem(CashFlowItemType.TRADE, s.time, s.count, s.price, s.currency))
                cashflow.append(CashFlowItem(CashFlowItemType.COMMISSION, s.time, -1, s.commission, s.currency))
                if __debug__:
                    income = s.count * s.price
                    outcome = 0

                while s.count and buy:
                    b = buy[0]
                    b.count -= s.count
                    if b.count <= 0:
                        if __debug__:
                            outcome += (b.count + s.count) * b.price
                        cashflow.append(CashFlowItem(CashFlowItemType.TRADE, b.time, -(b.count + s.count), b.price, s.currency))
                        cashflow.append(CashFlowItem(CashFlowItemType.COMMISSION, b.time, -1, b.commission, s.currency))  # full cost
                        s.count = -b.count  # left count
                        del buy[0]
                    else:
                        if __debug__:
                            outcome += s.count * b.price
                        cashflow.append(CashFlowItem(CashFlowItemType.TRADE, b.time, -s.count, b.price, s.currency))
                        ratio = Decimal(s.count / (s.count + b.count))
                        cashflow.append(CashFlowItem(CashFlowItemType.COMMISSION, b.time, -1, round(b.commission * ratio, 2), s.currency))  # partial cost
                        b.commission -= round(b.commission * ratio, 2)
                        break
                if __debug__:
                    pl = pl + income - outcome
            self.cashflows[symbol] = cashflow

            if __debug__:  # validate data
                trade_income = sum([cf.count * cf.price for cf in cashflow if cf.count > 0 and cf.type == CashFlowItemType.TRADE])
                trade_cost = -sum([cf.count * cf.price for cf in cashflow if cf.count < 0 and cf.type == CashFlowItemType.TRADE])
                crc_income = sum([s.volume for s in sell])
                if trade_income != crc_income:
                    raise Exception(f"income doesn't math for symbol {symbol}")
                if pl != trade_income - trade_cost:
                    raise Exception(f"PL doesn't math for symbol {symbol}")


def ls(text: str):
    text = text.strip() + " "
    print()
    #print("-" * (120 + 2))
    print("* " + text + "*" * (10 - len(text)))


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    CACHE = load_cache(".cache")
    account = Account()
    transaction_log = {}
    with open(r"TR.csv", newline='', encoding="utf-16") as csvfile:
        reader = csv.reader(csvfile, delimiter='\t')
        next(reader, None)
        for row in reader:
            symbol = Transaction.get_symbol(row)
            tr = transaction_log.get(symbol, None)
            if not tr:
                transaction_log[symbol] = []
                tr = transaction_log[symbol]
            tr.append(Transaction.from_cvs_row(row))

    account.init_cash_flow(transaction_log)
    cashflows = account.cashflows

    ls("FOREGIN")
    table = [["symbol", "currency", "income", "cost", "commission", "P/L"]]
    for symbol, cashflow in cashflows.items():
        trade_income = sum([cf.count * cf.price for cf in cashflow if cf.count > 0 and cf.type == CashFlowItemType.TRADE])
        trade_cost = -sum([cf.count * cf.price for cf in cashflow if cf.count < 0 and cf.type == CashFlowItemType.TRADE])
        commission_cost = -sum([cf.count * cf.price for cf in cashflow if cf.type == CashFlowItemType.COMMISSION])
        assert sum([cf.count * cf.price for cf in cashflow if cf.count > 0 and cf.type == CashFlowItemType.COMMISSION]) == 0, f"commission_cost != 0"

        if cashflow:  # output only items with data
            table.append([symbol, cashflow[0].currency, trade_income, trade_cost, commission_cost, trade_income - trade_cost - commission_cost])

    print(tabulate(table, headers="firstrow", floatfmt=".2f", tablefmt="presto"))

    ls("PLN")
    table = [["symbol", "income", "cost", "commission", "P/L"]]
    for symbol, cashflow in cashflows.items():
        trade_income = sum([round(cf.count * cf.price * get_nbp_day_before(cf.currency, cf.time), 2) for cf in cashflow if cf.count > 0 and cf.type == CashFlowItemType.TRADE])
        trade_cost = -sum([round(cf.count * cf.price * get_nbp_day_before(cf.currency, cf.time), 2) for cf in cashflow if cf.count < 0 and cf.type == CashFlowItemType.TRADE])
        commission_cost = -sum([round(cf.count * cf.price * get_nbp_day_before(cf.currency, cf.time), 2) for cf in cashflow if cf.type == CashFlowItemType.COMMISSION])

        if cashflow:  # output only items with data
            table.append([symbol, trade_income, trade_cost, commission_cost, trade_income - trade_cost - commission_cost])

    print(tabulate(table, headers="firstrow", floatfmt=".2f", tablefmt="presto"))

    trade_income = sum([round(cf.count * cf.price * get_nbp_day_before(cf.currency, cf.time), 2) for key in cashflows for cf in cashflows[key] if cf.count > 0 and cf.type == CashFlowItemType.TRADE])
    trade_cost = -sum([round(cf.count * cf.price * get_nbp_day_before(cf.currency, cf.time), 2) for key in cashflows for cf in cashflows[key] if cf.count < 0])

    ls("TOTAL PLN")
    table = [["income", "cost", "P/L"]]
    table.append([trade_income, trade_cost, trade_income - trade_cost])
    print(tabulate(table, headers="firstrow", floatfmt=".2f", tablefmt="presto"))

    save_cache(".cache", CACHE)
