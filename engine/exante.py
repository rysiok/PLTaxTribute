from datetime import datetime
from decimal import Decimal
from typing import List

from engine.account import AccountBase
from engine.transaction import TransactionSide, TradeTransaction, DividendTransaction, CashFlowItem, CashFlowItemType
from engine.utils import ParseError


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


class ExanteAccount(AccountBase):
    """
    - Load transaction log into an array from CSV file and sort it ascending by transaction id.
    - For each transaction check operation type. Based on it create TradeTransaction or DividendTransaction. Fill missing data (ie. price, commission, tax)
        based on data in following transactions. Store Transactions list in dictionary using symbol as a key (group Transaction by symbol)
    - For each symbol process sell Transactions and create CashFlowItem (TRADE, COMMISSION, DIVIDEND, TAX), based on FIFO method,
        getting amount in PLN based D-1 exchange rate, where transaction time is T+0.  Store each CashFlowItem list in a dictionary using symbol as a key.

    During sum calculations Use round(2) on CashFlowItem level after multiplication count * price * pln exchange rate before sum. Decimal is used for
    floating point calculations.

    """

    def __init__(self, warning_handler=None):
        super().__init__(warning_handler)

    def load_transaction_log(self, file):
        super()._load_transaction_log(file, "utf=16", '\t', lambda i: i[Column.ID])

    def _parse(self, row: List[str]):
        op_type = row[Column.OP_TYPE]
        supported_op_types = ("TRADE", "COMMISSION", "DIVIDEND", "TAX")

        if op_type == "FUNDING/WITHDRAWAL":
            return

        if op_type not in supported_op_types:
            raise ParseError(f"Unsupported transaction type {op_type}.")

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
            self.transaction_log[symbol] = [log_item] if symbol not in self.transaction_log.keys() else self.transaction_log[symbol] + [log_item]
            return

        if op_type == "DIVIDEND":
            value = Decimal(row[Column.SUM])
            log_item = DividendTransaction(time=time, value=value, symbol=symbol, currency=asset)
            self.transaction_log[symbol] = [log_item] if symbol not in self.transaction_log.keys() else self.transaction_log[symbol] + [log_item]
            return

        # another row of transaction object
        last_log_item = self.transaction_log[symbol][-1]

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

    def _load_cash_flow(self, nbp):
        for symbol, tr in self.transaction_log.items():
            sell = [t for t in tr if t.side == TransactionSide.SELL]
            buy = [t for t in tr if t.side == TransactionSide.BUY]
            dividend = [t for t in tr if t.side == TransactionSide.DIVIDEND]

            if not buy and not dividend:
                self._warning_handler(f"No BUY transactions for symbol: {symbol}.")
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

            self.cash_flows[symbol] = cashflow

    def get_foreign(self):
        table = [["symbol", "currency", "income", "cost", "P/L", "(commission)"]]
        for symbol, cashflow in self.cash_flows.items():
            if cashflow:  # output only items with data
                trade_income = sum([cf.count * cf.price for cf in cashflow if cf.count > 0 and cf.type == CashFlowItemType.TRADE])
                if trade_income:
                    trade_cost = -sum([cf.count * cf.price for cf in cashflow if cf.count < 0 and cf.type == CashFlowItemType.TRADE])
                    commission_cost = -sum([cf.count * cf.price for cf in cashflow if cf.type == CashFlowItemType.COMMISSION])
                    assert sum(
                        [cf.count * cf.price for cf in cashflow if cf.count > 0 and cf.type == CashFlowItemType.COMMISSION]) == 0, f"commission_cost != 0"

                    table.append(
                        [symbol, cashflow[0].currency, trade_income, trade_cost + commission_cost, trade_income - trade_cost - commission_cost,
                         commission_cost])
        return table

    def get_pln(self):
        table = [["symbol", "income", "cost", "P/L", "(commission)"]]
        total_trade_income = 0
        total_trade_cost = 0

        for symbol, cashflow in self.cash_flows.items():
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
        trade_income = sum([round(cf.count * cf.price * cf.pln, 2) for key in self.cash_flows for cf in self.cash_flows[key] if
                            cf.count > 0 and cf.type == CashFlowItemType.TRADE])
        trade_cost = -sum([round(cf.count * cf.price * cf.pln, 2) for key in self.cash_flows for cf in self.cash_flows[key] if cf.count < 0])
        table.append([trade_income, trade_cost, trade_income - trade_cost])
        return table

    def get_dividends(self):
        table = [["symbol", "currency", "income", "paid tax", "%"]]
        for symbol, cashflow in self.cash_flows.items():
            if cashflow:  # output only items with data
                income = sum([cf.price for cf in cashflow if cf.type == CashFlowItemType.DIVIDEND])
                tax = sum([cf.price for cf in cashflow if cf.type == CashFlowItemType.TAX])
                if income > 0:
                    percent = round(tax / income * 100)
                    table.append([symbol, cashflow[0].currency, income, tax, percent])
        return table

    def get_dividends_pln(self):
        table = [["income", "paid tax\r[PIT38 G45]", "%", "total to pay (19%)\r[PIT38 G46]", "left to pay (19%)\r[PIT38 G47]"]]
        income = sum([round(cf.count * cf.price * cf.pln, 2) for key in self.cash_flows for cf in self.cash_flows[key] if cf.type == CashFlowItemType.DIVIDEND])
        paid_tax = sum([round(cf.count * cf.price * cf.pln, 2) for key in self.cash_flows for cf in self.cash_flows[key] if cf.type == CashFlowItemType.TAX])
        if income > 0:
            percent = round(paid_tax / income * 100)
            tax = round(income * Decimal("0.19"), 2)
            left_to_pay = round(tax - paid_tax)
            table.append([income, paid_tax, percent, tax, left_to_pay])
        return table
