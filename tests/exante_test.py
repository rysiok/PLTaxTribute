import os
from datetime import datetime
from decimal import Decimal

import pytest

from engine.exante import ExanteAccount
from engine.transaction import TradeTransaction, TransactionSide, DividendTransaction
from engine.utils import ParseError
from tests import BASE_DIR
from tests.setup import nbp, nbp_real, exante_account, nbp_mock

_ = (nbp, nbp_real, exante_account, nbp_mock,)
del _


def test_parser_skip_op_types():
    account = ExanteAccount()
    supported_op_types = ("FUNDING/WITHDRAWAL",)
    for op_type in supported_op_types:
        data = ["", "", "SYMBOL", "ISIN", op_type, "2020-01-01 00:00:00", "1000", "USD", "", ""]
        account._parse(data)
        assert len(account.transaction_log) == 0


def test_parser_unsupported_op_types():
    account = ExanteAccount()
    supported_op_types = ("AUTOCONVERSION", "BLAH BLAH BLAH")
    for op_type in supported_op_types:
        data = ["", "", "SYMBOL", "ISIN", op_type, "2020-01-01 00:00:00", "1000", "USD", "", ""]
        with pytest.raises(ParseError, match=r".*" + op_type + r".*"):
            account._parse(data)


def test_parser_valid_trade():
    account = ExanteAccount()
    data = [
        ["1", "", "ABC", "ISIN", "TRADE", "2020-01-01 00:00:00", "150", "ABC", "", ""],
        ["2", "", "ABC", "None", "TRADE", "2020-01-01 00:00:00", "1500", "USD", "", ""],
        ["3", "", "ABC", "None", "COMMISSION", "2020-01-01 00:00:00", "-3.0", "USD", "", ""],
        ["4", "", "ABC", "ISIN", "TRADE", "2020-01-01 00:00:00", "-150", "ABC", "", ""],
        ["5", "", "ABC", "None", "TRADE", "2020-01-01 00:00:00", "1500", "USD", "", ""],
        ["6", "", "ABC", "None", "COMMISSION", "2020-01-01 00:00:00", "-3.0", "USD", "", ""],
    ]

    for row in data:
        account._parse(row)

    tr = account.transaction_log.get("ABC")
    assert tr is not None
    assert len(tr) == 2
    assert type(tr[0]) is TradeTransaction
    assert tr[0].time == datetime.fromisoformat("2020-01-01 00:00:00")
    assert tr[0].currency == "USD"
    assert tr[0].symbol == "ABC"

    assert tr[0].side == TransactionSide.BUY
    assert tr[0].count == 150
    assert tr[0].price == Decimal("10")
    assert tr[0].commission == Decimal("3")

    assert type(tr[1]) is TradeTransaction
    assert tr[1].side == TransactionSide.SELL


def test_parser_valid_dividend():
    account = ExanteAccount()

    data = [
        ["1", "", "ABC", "None", "DIVIDEND", "2020-01-01 00:00:00", "10", "USD", "", ""],
        ["2", "", "ABC", "None", "TAX", "2020-01-01 00:00:00", "-2", "USD", "", ""],
    ]

    for row in data:
        account._parse(row)

    tr = account.transaction_log.get("ABC")
    assert tr is not None
    assert len(tr) == 1
    assert type(tr[0]) is DividendTransaction
    assert tr[0].time == datetime.fromisoformat("2020-01-01 00:00:00")
    assert tr[0].side == TransactionSide.DIVIDEND
    assert tr[0].symbol == "ABC"
    assert tr[0].value == Decimal("10")
    assert tr[0].tax == Decimal("2")
    assert tr[0].currency == "USD"


def test_parse_transaction_log():
    account = ExanteAccount()
    data = [
        ["1", "", "ABC", "ISIN", "TRADE", "2020-01-01 00:00:00", "150", "ABC", "", ""],
        ["3", "", "ABC", "None", "COMMISSION", "2020-01-01 00:00:00", "-3.0", "USD", "", ""],
        ["2", "", "ABC", "None", "TRADE", "2020-01-01 00:00:00", "1500", "USD", "", ""],
    ]
    account._parse_transaction_log(data, lambda i: i[0])
    tr = account.transaction_log.get("ABC")
    assert tr is not None
    assert len(tr) == 1


def test_load_transaction_log(capfd):
    account = ExanteAccount(lambda e: print(e))
    account.load_transaction_log(os.path.join(BASE_DIR, "exante.csv"))
    captured = capfd.readouterr()
    assert "Unsupported transaction type AUTOCONVERSION." in captured.out


def test_load_cash_flow(nbp_mock):
    message = None

    def handler(e):
        nonlocal message
        message = e

    account = ExanteAccount(handler)
    data = [
        ["1", "", "ABC", "ISIN", "TRADE", "2020-01-01 00:00:00", "-150", "ABC", "", ""],
        ["2", "", "ABC", "None", "TRADE", "2020-01-01 00:00:00", "1500", "USD", "", ""],
        ["3", "", "ABC", "None", "COMMISSION", "2020-01-01 00:00:00", "-3.0", "USD", "", ""],
    ]
    account._parse_transaction_log(data, lambda i: i[0])
    account._load_cash_flow(nbp_mock)
    assert message == f"No BUY transactions for symbol: ABC."
    assert len(account.cash_flows) == 0

def test_get_foreign(exante_account):
    t = exante_account.get_foreign()[1:]  # skip header
    assert len(t) == 2
    assert t[0][0] == 'ABC', "symbol"
    assert t[0][2] == Decimal("1000"), "income"
    assert t[0][3] == Decimal("504"), "cost"
    assert t[0][4] == Decimal("496"), "P/L"
    assert t[0][5] == Decimal("4"), "commission"
    assert t[0][2] - t[0][3] == Decimal("496"), "P/L"

    assert t[1][0] == 'XYZ', "symbol"
    assert t[1][2] == Decimal("100"), "income"
    assert t[1][3] == Decimal("102"), "cost"
    assert t[1][4] == Decimal("-2"), "P/L"
    assert t[1][5] == Decimal("2"), "commission"


def test_get_pln(exante_account):
    t = exante_account.get_pln()[1:]  # skip header
    assert len(t) == 4
    assert t[0][0] == 'ABC', "symbol"
    assert t[0][1] == Decimal("2000"), "income"
    assert t[0][2] == Decimal("1008"), "cost"
    assert t[0][3] == Decimal("992"), "P/L"
    assert t[0][4] == Decimal("8"), "commission"
    assert t[0][1] - t[0][2] == t[0][3], "P/L"

    assert t[1][0] == 'XYZ', "symbol"
    assert t[1][1] == Decimal("200"), "income"
    assert t[1][2] == Decimal("204"), "cost"
    assert t[1][3] == Decimal("-4"), "P/L"
    assert t[1][4] == Decimal("4"), "commission"
    assert t[1][1] - t[1][2] == t[1][3], "P/L"

    assert t[3][0] == 'TOTAL', "symbol"
    assert t[3][1] == Decimal("2200"), "income"
    assert t[3][2] == Decimal("1212"), "cost"
    assert t[3][3] == Decimal("988"), "P/L"
    assert t[3][1] - t[3][2] == t[3][3], "P/L"

    assert t[0][1] + t[1][1] == Decimal("2200"), "income"
    assert t[0][2] + t[1][2] == Decimal("1212"), "cost"
    assert t[0][3] + t[1][3] == Decimal("988"), "P/L"


def test_get_pln_total(exante_account):
    t = exante_account.get_pln_total()[1:]  # skip header
    assert len(t) == 1
    assert t[0][0] == Decimal("2200"), "income"
    assert t[0][1] == Decimal("1212"), "cost"
    assert t[0][2] == Decimal("988"), "P/L"
    assert t[0][0] - t[0][1] == t[0][2], "P/L"


def test_dividends(exante_account):
    t = exante_account.get_dividends()[1:]  # skip header
    assert len(t) == 1
    assert t[0][0] == 'QQQ', "symbol"
    assert t[0][2] == Decimal("60.10"), "income"
    assert t[0][3] == Decimal("2.2"), "tax"
    assert round(t[0][3] / t[0][2] * 100) == Decimal("4"), "%"


def test_dividends_pln(exante_account):
    t = exante_account.get_dividends_pln()[1:]  # skip header
    assert len(t) == 1
    assert t[0][0] == Decimal("120.20"), "income"
    assert t[0][1] == Decimal("4.40"), "paid tax"
    assert round(t[0][1] / t[0][0] * 100) == Decimal("4"), "%"
    assert round(t[0][0] * Decimal("0.19"), 2) == Decimal("22.84"), "total to pay"
    assert round(round(t[0][0] * Decimal("0.19"), 2) - t[0][1]) == Decimal("18"), "left to pay"
