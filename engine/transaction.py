from abc import ABCMeta
from datetime import datetime
from decimal import Decimal
from enum import Enum


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


class CashFlowItem:
    def __init__(self, type: CashFlowItemType, time: datetime, count: int, price: Decimal, currency: str, pln: Decimal):
        self.type = type
        self.time = time
        self.count = count
        self.price = price
        self.currency = currency
        self.pln = pln


class TransactionBase(metaclass=ABCMeta):
    def __init__(self, time: datetime, side: TransactionSide, symbol: str):
        self.time = time
        self.side = side
        self.symbol = symbol


class TradeTransaction(TransactionBase):
    def __init__(self, time: datetime, side: TransactionSide, symbol: str, count: int, price: Decimal = None, currency: str = None, commission: Decimal = None):
        super().__init__(time, side, symbol)
        self.price = price
        self.currency = currency
        self.count = count
        self.commission = commission


class DividendTransaction(TransactionBase):
    def __init__(self, time: datetime, symbol: str, value: Decimal, currency: str, tax: Decimal = None):
        super().__init__(time, TransactionSide.DIVIDEND, symbol)
        self.value = value
        self.tax = tax
        self.currency = currency
