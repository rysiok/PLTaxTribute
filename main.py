import csv
import requests
import pickle
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum


def save_cache(filename, CACHE):
    if not filename:
        return
    try:
        with open(filename, "wb") as f:
            pickle.dump(CACHE, f)
    except:
        pass


def load_cache(filename):
    if not filename:
        return
    try:
        with open(filename, "rb") as f:
            return pickle.load(f)
    except:
        return {}


class TransactionType(Enum):
    BUY = 1
    SELL = 2


class CashFlowItemType(Enum):
    COMMISSION = 1
    TRADE = 2
    PL = 3


class TR:
    TIME = 0
    SIDE = 2
    SYMBOL = 3
    PRICE = 6
    CURRENCY = 7
    COUNT = 8
    COMMISSION = 9
    VOLUME = 12


class Transaction:
    def __init__(self, time: datetime, side: TransactionType, price: Decimal, currency: str, count: int, commission: Decimal, volume: Decimal):
        self.time = time
        self.side = side
        self.price = price
        self.currency = currency
        self.count = count
        self.commission = commission
        self.volume = volume

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


def ls(text: str):
    print("-" * (120 + 2))
    print("- " + text + "-" * (120 - len(text)))


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    CACHE = load_cache(".cache")
    tr = {}
    with open(r"TR.csv", newline='', encoding="utf-16") as csvfile:
        reader = csv.reader(csvfile, delimiter='\t')
        next(reader, None)
        for row in reader:
            transactions = tr.get(row[TR.SYMBOL], None)
            if not transactions:
                tr[row[TR.SYMBOL]] = []
                transactions = tr[row[TR.SYMBOL]]
            transactions.append(Transaction(datetime.fromisoformat(row[TR.TIME]),
                                            TransactionType.BUY if row[TR.SIDE] == "buy" else TransactionType.SELL,
                                            Decimal(row[TR.PRICE]), row[TR.CURRENCY], int(row[TR.COUNT]), Decimal(row[TR.COMMISSION]),
                                            Decimal(row[TR.VOLUME])
                                            ))
    cashflows = {}
    for symbol, transactions in tr.items():
        transactions.sort(key=lambda x: x.time)

        sell = [t for t in transactions if t.side == TransactionType.SELL]
        buy = [t for t in transactions if t.side == TransactionType.BUY]
        cashflow = []
        pl = 0
        for s in sell:
            cashflow.append(CashFlowItem(CashFlowItemType.TRADE, s.time, s.count, s.price, s.currency))
            cashflow.append(CashFlowItem(CashFlowItemType.COMMISSION, s.time, -1, s.commission, s.currency))
            income = s.count * s.price
            outcome = 0

            while s.count and buy:
                b = buy[0]
                b.count -= s.count
                if b.count <= 0:
                    outcome += (b.count + s.count) * b.price
                    cashflow.append(CashFlowItem(CashFlowItemType.TRADE, b.time, -(b.count + s.count), b.price, s.currency))
                    cashflow.append(CashFlowItem(CashFlowItemType.COMMISSION, b.time, -1, b.commission, s.currency))  # full cost
                    s.count = -b.count  # left count
                    del buy[0]
                else:
                    outcome += s.count * b.price
                    cashflow.append(CashFlowItem(CashFlowItemType.TRADE, b.time, -s.count, b.price, s.currency))
                    ratio = Decimal(s.count / (s.count + b.count))
                    cashflow.append(CashFlowItem(CashFlowItemType.COMMISSION, b.time, -1, round(b.commission * ratio, 2), s.currency))  # partial cost
                    b.commission -= round(b.commission * ratio, 2)
                    break
            pl = pl + income - outcome
        cashflows[symbol] = cashflow

        if __debug__:  # validate data
            trade_income = sum([cf.count * cf.price for cf in cashflow if cf.count > 0 and cf.type == CashFlowItemType.TRADE])
            trade_cost = -sum([cf.count * cf.price for cf in cashflow if cf.count < 0 and cf.type == CashFlowItemType.TRADE])
            crc_income = sum([s.volume for s in sell])
            if trade_income != crc_income:
                raise Exception(f"income doesn't math for symbol {symbol}")
            if pl != trade_income - trade_cost:
                raise Exception(f"PL doesn't math for symbol {symbol}")

    ls("USD")
    for symbol, cashflow in cashflows.items():
        trade_income = sum([cf.count * cf.price for cf in cashflow if cf.count > 0 and cf.type == CashFlowItemType.TRADE])
        trade_cost = -sum([cf.count * cf.price for cf in cashflow if cf.count < 0 and cf.type == CashFlowItemType.TRADE])
        commission_cost = -sum([cf.count * cf.price for cf in cashflow if cf.type == CashFlowItemType.COMMISSION])
        assert sum([cf.count * cf.price for cf in cashflow if cf.count > 0 and cf.type == CashFlowItemType.COMMISSION]) == 0, f"commission_cost != 0"

        print(f"** {symbol:15} : income {trade_income:10} : cost {trade_cost:10} : commission : {commission_cost:10} : P/L {trade_income - trade_cost - commission_cost:10}")

    ls("PLN")
    for symbol, cashflow in cashflows.items():
        trade_income = sum([round(cf.count * cf.price * get_nbp_day_before(cf.currency, cf.time), 2) for cf in cashflow if cf.count > 0 and cf.type == CashFlowItemType.TRADE])
        trade_cost = -sum([round(cf.count * cf.price * get_nbp_day_before(cf.currency, cf.time), 2) for cf in cashflow if cf.count < 0 and cf.type == CashFlowItemType.TRADE])
        commission_cost = -sum([round(cf.count * cf.price * get_nbp_day_before(cf.currency, cf.time), 2) for cf in cashflow if cf.type == CashFlowItemType.COMMISSION])
        print(f"** {symbol:15} : income {trade_income:10} : cost {trade_cost:10} : commission : {commission_cost:10} : P/L {trade_income - trade_cost - commission_cost:10}")

    trade_income = sum([round(cf.count * cf.price * get_nbp_day_before(cf.currency, cf.time), 2) for key in cashflows for cf in cashflows[key] if cf.count > 0 and cf.type == CashFlowItemType.TRADE])
    trade_cost = -sum([round(cf.count * cf.price * get_nbp_day_before(cf.currency, cf.time), 2) for key in cashflows for cf in cashflows[key] if cf.count < 0])

    ls("TOTAL PLN")
    print(f"** income {trade_income:10} : cost {trade_cost:10} : P/L {trade_income - trade_cost:10}")

    save_cache(".cache", CACHE)
