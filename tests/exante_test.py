import os
from datetime import datetime
from decimal import Decimal

import pytest

from engine.exante import ExanteAccount
from engine.transaction import TradeTransaction, TransactionSide, DividendTransaction
from engine.utils import ParseError
from tests import BASE_DIR
from tests.setup import nbp, nbp_real, nbp_mock

_ = (nbp, nbp_real, nbp_mock,)
del _


@pytest.fixture
def exante_account(nbp_mock):
    account = ExanteAccount()
    data = [
        ["01", "", "ABC", "ISIN", "TRADE", "2020-01-01 00:00:00", "150", "ABC", "", ""],
        ["02", "", "ABC", "None", "TRADE", "2020-01-01 00:00:00", "1500", "USD", "", ""],
        ["03", "", "ABC", "None", "COMMISSION", "2020-01-01 00:00:00", "-3.0", "USD", "", ""],
        ["04", "", "ABC", "ISIN", "TRADE", "2020-02-01 00:00:00", "-50", "ABC", "", ""],
        ["05", "", "ABC", "None", "TRADE", "2020-02-01 00:00:00", "1000", "USD", "", ""],
        ["06", "", "ABC", "None", "COMMISSION", "2020-02-01 00:00:00", "-3.0", "USD", "", ""],

        ["07", "", "XYZ", "ISIN", "TRADE", "2020-01-01 00:00:00", "10", "XYZ", "", ""],
        ["08", "", "XYZ", "None", "TRADE", "2020-01-01 00:00:00", "100", "USD", "", ""],
        ["09", "", "XYZ", "None", "COMMISSION", "2020-01-01 00:00:00", "1", "USD", "", ""],
        ["10", "", "XYZ", "ISIN", "TRADE", "2021-02-01 00:00:00", "-10", "XYZ", "", ""],
        ["11", "", "XYZ", "None", "TRADE", "2021-02-01 00:00:00", "100", "USD", "", ""],
        ["12", "", "XYZ", "None", "COMMISSION", "2021-02-01 00:00:00", "1", "USD", "", ""],

        ["13", "", "QQQ", "None", "DIVIDEND", "2020-01-01 00:00:00", "60.10", "USD", "", ""],
        ["14", "", "QQQ", "None", "TAX", "2020-01-01 00:00:00", "-2.2", "USD", "", ""],
        ["15", "", "QQQ", "None", "DIVIDEND", "2021-01-01 00:00:00", "120.2", "USD", "", ""],
        ["16", "", "QQQ", "None", "TAX", "2021-01-01 00:00:00", "-4.4", "USD", "", ""],
    ]

    account._parse_transaction_log(data)
    account.init_cash_flow(nbp_mock)
    return account


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
        ["4", "", "ABC", "None", "AUTOCONVERSION", "2020-01-01 00:00:00", "1500", "USD", "", ""],
    ]
    account._parse_transaction_log(data, lambda i: i[0])
    tr = account.transaction_log.get("ABC")
    assert tr is not None
    assert len(tr) == 1


def test_parse_transaction_log_multi_year():
    account = ExanteAccount()
    data = [
        ["1", "", "ABC", "ISIN", "TRADE", "2020-01-01 00:00:00", "150", "ABC", "", ""],
        ["2", "", "ABC", "None", "TRADE", "2020-01-01 00:00:00", "1500", "USD", "", ""],
        ["3", "", "ABC", "None", "COMMISSION", "2020-01-01 00:00:00", "-3.0", "USD", "", ""],
        ["4", "", "ABC", "ISIN", "TRADE", "2021-01-01 00:00:00", "150", "ABC", "", ""],
        ["5", "", "ABC", "None", "TRADE", "2021-01-01 00:00:00", "1500", "USD", "", ""],
        ["6", "", "ABC", "None", "COMMISSION", "2021-01-01 00:00:00", "-3.0", "USD", "", ""],
    ]
    account._parse_transaction_log(data, lambda i: i[0])
    tr = account.transaction_log.get("ABC")
    assert tr is not None
    assert len(tr) == 2


def test_load_transaction_log(capfd):
    account = ExanteAccount(lambda e: print(e))
    account.load_transaction_log(os.path.join(BASE_DIR, "exante.csv"))
    captured = capfd.readouterr()
    assert "Unsupported transaction type AUTOCONVERSION." in captured.out


def test_load_transaction_logs(capfd):
    account = ExanteAccount(lambda e: print(e))
    account.load_transaction_logs(os.path.join(BASE_DIR, "multi"))
    assert len(account.transaction_log['XYZ']) == 2


def test_load_cash_flow_no_buy(nbp_mock):
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


def test_load_cash_flow(nbp_mock):
    account = ExanteAccount()
    data = [
        ["1", "", "ABC", "ISIN", "TRADE", "2020-01-01 00:00:00", "150", "ABC", "", ""],
        ["2", "", "ABC", "None", "TRADE", "2020-01-01 00:00:00", "1500", "USD", "", ""],
        ["3", "", "ABC", "None", "COMMISSION", "2020-01-01 00:00:00", "-3.0", "USD", "", ""],
        ["4", "", "ABC", "ISIN", "TRADE", "2021-01-01 00:00:00", "-150", "ABC", "", ""],
        ["5", "", "ABC", "None", "TRADE", "2021-01-01 00:00:00", "1500", "USD", "", ""],
        ["6", "", "ABC", "None", "COMMISSION", "2021-01-01 00:00:00", "-3.0", "USD", "", ""],
    ]
    account._parse_transaction_log(data, lambda i: i[0])
    account._load_cash_flow(nbp_mock)
    assert len(account.cash_flows) == 1
    assert 'ABC' in account.cash_flows[2021].keys()
    assert len(account.cash_flows[2021]['ABC']) == 4


def test_load_cash_flow_multi_year(nbp_mock):
    account = ExanteAccount()
    data = [
        ["1", "", "ABC", "ISIN", "TRADE", "2020-01-01 00:00:00", "150", "ABC", "", ""],
        ["2", "", "ABC", "None", "TRADE", "2020-01-01 00:00:00", "1500", "USD", "", ""],
        ["3", "", "ABC", "None", "COMMISSION", "2020-01-01 00:00:00", "-3.0", "USD", "", ""],
        ["4", "", "ABC", "ISIN", "TRADE", "2020-01-01 00:00:00", "-50", "ABC", "", ""],
        ["5", "", "ABC", "None", "TRADE", "2020-01-01 00:00:00", "500", "USD", "", ""],
        ["6", "", "ABC", "None", "COMMISSION", "2020-01-01 00:00:00", "-1.0", "USD", "", ""],
        ["7", "", "ABC", "ISIN", "TRADE", "2021-01-01 00:00:00", "-100", "ABC", "", ""],
        ["8", "", "ABC", "None", "TRADE", "2021-01-01 00:00:00", "1000", "USD", "", ""],
        ["9", "", "ABC", "None", "COMMISSION", "2021-01-01 00:00:00", "-2.0", "USD", "", ""],
    ]
    account._parse_transaction_log(data, lambda i: i[0])
    account._load_cash_flow(nbp_mock)
    assert len(account.cash_flows) == 2
    assert 'ABC' in account.cash_flows[2020].keys()
    assert 'ABC' in account.cash_flows[2021].keys()
    assert len(account.cash_flows[2020]['ABC']) == 4
    assert len(account.cash_flows[2021]['ABC']) == 4


def test_get_foreign(exante_account):
    t = exante_account.get_foreign()[1:]  # skip header
    assert len(t) == 4
    idx = 0
    assert t[idx][0] == 2020, "year"

    idx += 1
    assert t[idx][0] == 'ABC', "symbol"
    assert t[idx][2] == Decimal("1000"), "income"
    assert t[idx][3] == Decimal("504"), "cost"
    assert t[idx][4] == Decimal("496"), "P/L"
    assert t[idx][5] == Decimal("4"), "commission"
    assert t[idx][2] - t[idx][3] == Decimal("496"), "P/L"

    idx += 1
    assert t[idx][0] == 2021, "year"

    idx += 1
    assert t[idx][0] == 'XYZ', "symbol"
    assert t[idx][2] == Decimal("100"), "income"
    assert t[idx][3] == Decimal("102"), "cost"
    assert t[idx][4] == Decimal("-2"), "P/L"
    assert t[idx][5] == Decimal("2"), "commission"


def test_get_pln(exante_account):
    t = exante_account.get_pln()[1:]  # skip header
    assert len(t) == 8

    idx = 0
    assert t[idx][0] == 2020, "year"

    idx += 1
    assert t[idx][0] == 'ABC', "symbol"
    assert t[idx][1] == Decimal("2000"), "income"
    assert t[idx][2] == Decimal("1008"), "cost"
    assert t[idx][3] == Decimal("992"), "P/L"
    assert t[idx][4] == Decimal("8"), "commission"
    assert t[idx][1] - t[idx][2] == t[idx][3], "P/L"

    idx += 2
    assert t[idx][0] == 'TOTAL 2020', "symbol"
    assert t[idx][1] == Decimal("2000"), "income"
    assert t[idx][2] == Decimal("1008"), "cost"
    assert t[idx][3] == Decimal("992"), "P/L"
    assert t[idx][1] - t[idx][2] == t[idx][3], "P/L"

    idx += 1
    assert t[idx][0] == 2021, "year"

    idx += 1
    assert t[idx][0] == 'XYZ', "symbol"
    assert t[idx][1] == Decimal("200"), "income"
    assert t[idx][2] == Decimal("204"), "cost"
    assert t[idx][3] == Decimal("-4"), "P/L"
    assert t[idx][4] == Decimal("4"), "commission"
    assert t[idx][1] - t[idx][2] == t[idx][3], "P/L"

    idx += 2
    assert t[idx][0] == 'TOTAL 2021', "symbol"
    assert t[idx][1] == Decimal("200"), "income"
    assert t[idx][2] == Decimal("204"), "cost"
    assert t[idx][3] == Decimal("-4"), "P/L"
    assert t[idx][1] - t[idx][2] == t[idx][3], "P/L"


def test_get_pln_total(exante_account):
    t = exante_account.get_pln_total()[1:]  # skip header
    assert len(t) == 2
    idx = 0
    assert t[idx][0] == 2020, "year"
    assert t[idx][1] == Decimal("2000"), "income"
    assert t[idx][2] == Decimal("1008"), "cost"
    assert t[idx][3] == Decimal("992"), "P/L"
    assert t[idx][1] - t[idx][2] == t[idx][3], "P/L"

    idx += 1
    assert t[idx][0] == 2021, "year"
    assert t[idx][1] == Decimal("200"), "income"
    assert t[idx][2] == Decimal("204"), "cost"
    assert t[idx][3] == Decimal("-4"), "P/L"
    assert t[idx][1] - t[idx][2] == t[idx][3], "P/L"


def test_dividends(exante_account):
    t = exante_account.get_dividends()[1:]  # skip header
    assert len(t) == 2
    idx = 0
    assert t[idx][0] == 2020, "year"
    assert t[idx][1] == 'QQQ', "symbol"
    assert t[idx][3] == Decimal("60.10"), "income"
    assert t[idx][4] == Decimal("2.2"), "tax"
    assert round(t[idx][4] / t[idx][3] * 100) == Decimal("4"), "%"

    idx += 1
    assert t[idx][0] == 2021, "year"
    assert t[idx][1] == 'QQQ', "symbol"
    assert t[idx][3] == Decimal("120.2"), "income"
    assert t[idx][4] == Decimal("4.4"), "tax"
    assert round(t[idx][4] / t[idx][3] * 100) == Decimal("4"), "%"


def test_dividends_pln(exante_account):
    t = exante_account.get_dividends_pln()[1:]  # skip header
    assert len(t) == 2
    idx = 0
    assert t[idx][0] == 2020, "year"
    assert t[idx][1] == Decimal("120.20"), "income"
    assert t[idx][2] == Decimal("4.40"), "paid tax"
    assert round(t[idx][2] / t[idx][1] * 100) == Decimal("4"), "%"
    assert round(t[idx][1] * Decimal("0.19"), 2) == Decimal("22.84"), "total to pay"
    assert round(round(t[idx][1] * Decimal("0.19"), 2) - t[idx][2]) == Decimal("18"), "left to pay"
