# Mintos transaction log column positions
from datetime import datetime
from decimal import Decimal
from typing import List

from engine.account import AccountBase
from engine.transaction import DividendTransaction, CashFlowItem, CashFlowItemType, TransactionSide


class Column:
    TIME = 0
    DETAILS = 2
    TURNOVER = 3
    CURRENCY = 5


class MintosAccount(AccountBase):
    """
1. Load transaction log into an array from CSV file and sort it ascending by transaction date
2. For each transaction check transaction type. Treat Mintos income transactions as DividendTransaction.
   Store Transactions list in dictionary using symbol as a key (one transaction group)
3. For each Transaction create CashFlowItem (DIVIDEND), getting amount in PLN based D-1 exchange rate,
   where transaction time is T+0.  Store each CashFlowItem list in a dictionary.

    During sum calculations Use round(2) on CashFlowItem level after multiplication count * price * pln exchange rate before sum. Decimal is used for
    floating pont calculations.

    """

    def load_transaction_log(self, file):
        super()._load_transaction_log(file, "ASCII", ',', lambda i: i[Column.TIME])

    def _parse(self, row: List[str]):
        if len(row) == 1:  # skip invalid entries
            return
        details = row[Column.DETAILS].lower()

        include = ("interest received",
                   "late fees received",
                   "refer a friend bonus"
                   # "secondary market fee",
                   # "discount/premium for secondary market transaction",
                   )

        if all([i not in details for i in include]):
            return

        time = datetime.fromisoformat(row[Column.TIME])
        value = Decimal(row[Column.TURNOVER])
        currency = row[Column.CURRENCY]
        symbol = "Mintos"
        log_item = DividendTransaction(time=time, value=value, symbol=symbol, currency=currency)
        self.transaction_log[symbol] = [log_item] if symbol not in self.transaction_log.keys() else self.transaction_log[symbol] + [log_item]

    def _load_cash_flow(self, nbp):
        for symbol, tr in self.transaction_log.items():
            dividend = [t for t in tr if t.side == TransactionSide.DIVIDEND]
            cashflow = []
            for d in dividend:
                pln = nbp.get_nbp_day_before(d.currency, d.time)
                cashflow.append(CashFlowItem(CashFlowItemType.DIVIDEND, d.time, 1, d.value, d.currency, pln))

            self.cash_flows[symbol] = cashflow

    def get_foreign(self):
        table = [["", "currency", "income"]]
        for symbol, cashflow in self.cash_flows.items():
            if cashflow:  # output only items with data
                income = sum([cf.price for cf in cashflow if cf.type == CashFlowItemType.DIVIDEND])
                if income > 0:
                    table.append([symbol, cashflow[0].currency, income])
        return table

    def get_pln(self):
        table = [["income", "total to pay (19%)\r[PIT38 G46]", "tax (19%)\r[PIT38 G47]"]]
        income = round(sum([cf.price * cf.pln for key in self.cash_flows for cf in self.cash_flows[key] if cf.type == CashFlowItemType.DIVIDEND]), 2)
        if income > 0:
            tax = round(income * Decimal("0.19"), 2)
            table.append([income, tax, round(tax)])
        return table
