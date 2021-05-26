import os
from datetime import datetime
from decimal import Decimal

from engine.mintos import MintosAccount
from engine.transaction import DividendTransaction
from tests import BASE_DIR
from tests.setup import nbp, nbp_real, mintos_account, nbp_mock

_ = (nbp, nbp_real, mintos_account, nbp_mock,)
del _


def test_parser():
    account = MintosAccount()
    data = [
        ["2020-01-01 00:00:01", "1", "Loan 21157138-01 - interest received", "2.5E-5", "", "EUR"],
        ["2020-01-01 00:00:02", "1", "Loan 21157138-01 - late fees received", "1.25E-5", "", "EUR"],
        ["2020-01-01 00:00:03", "1", "Loan 21157138-01 - interest received", "20.000000", "", "EUR"],
        ["2020-01-01 00:00:04", "1", "Loan 21157138-01 - secondary market fee", "20.000000", "", "EUR"],
        ["2020-01-01 00:00:05", "1", "Loan 21157138-01 - discount/premium for secondary market transaction", "20.000000", "", "EUR"],
        ["invalid"],
    ]

    for row in data:
        account._parse(row)

    tr = account.transaction_log.get("Mintos")
    assert tr is not None
    assert len(tr) == 3
    assert all(map(lambda t: type(t) is DividendTransaction, tr))
    assert tr[0].time == datetime.fromisoformat("2020-01-01 00:00:01")
    assert tr[0].currency == "EUR"
    assert tr[0].symbol == "Mintos"
    assert tr[0].value == Decimal("0.0000250")
    assert tr[1].value == Decimal("0.0000125")
    assert tr[2].value == Decimal("20")


def test_parse_transaction_log():
    account = MintosAccount()
    data = [
        ["2020-01-01 00:00:03", "1", "Loan 21157138-01 - interest received", "20.000000", "", "EUR"],
        ["2020-01-01 00:00:02", "1", "Loan 21157138-01 - late fees received", "1.25E-5", "", "EUR"],
        ["2020-01-01 00:00:01", "1", "Loan 21157138-01 - interest received", "2.5E-5", "", "EUR"],
        ["invalid"],
    ]
    account._parse_transaction_log(data, lambda i: i[0])
    tr = account.transaction_log.get("Mintos")
    assert tr is not None
    assert len(tr) == 3
    assert tr[0].time == datetime.fromisoformat("2020-01-01 00:00:01")


def test_load_transaction_log():
    account = MintosAccount()
    account.load_transaction_log(os.path.join(BASE_DIR, "mintos.csv"))
    assert len(account.transaction_log["Mintos"]) == 4


def test_load_cash_flow(nbp_mock):
    account = MintosAccount()
    data = [
        ["2020-01-01 00:00:01", "1", "Loan 21157138-01 - interest received", "2.5E-5", "", "EUR"],
        ["2020-01-01 00:00:02", "1", "Loan 21157138-01 - late fees received", "1.25E-5", "", "EUR"],
        ["2020-01-01 00:00:03", "1", "Loan 21157138-01 - interest received", "20.000000", "", "EUR"],
    ]
    account._parse_transaction_log(data, lambda i: i[0])
    account._load_cash_flow(nbp_mock)
    assert len(account.cash_flows["Mintos"]) == 3


def test_get_foreign(mintos_account):
    t = mintos_account.get_foreign()[1:]  # skip header
    assert len(t) == 1
    assert t[0][1] == "EUR", "currency"
    assert t[0][2] == Decimal("20.0028875"), "income"


def test_get_pln(mintos_account):
    t = mintos_account.get_pln()[1:]  # skip header
    assert len(t) == 1
    assert t[0][0] == Decimal("40.01"), "income"

    assert round(t[0][0] * Decimal("0.19"), 2) == Decimal("7.60"), "total to pay"
    assert round(t[0][0] * Decimal("0.19"), 0) == Decimal("8"), "tax"
