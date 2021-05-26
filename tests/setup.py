import os
from datetime import datetime

import pytest

from engine.NBP import NBP
from engine.exante import ExanteAccount
from engine.mintos import MintosAccount
from tests import BASE_DIR

test_cache_file = os.path.join(BASE_DIR, ".test_cache")

@pytest.fixture
def nbp():
    if os.path.exists(test_cache_file):
        os.remove(test_cache_file)
    yield NBP(test_cache_file)
    # clean up
    if os.path.exists(test_cache_file):
        os.remove(test_cache_file)


@pytest.fixture
def nbp_real():
    return NBP(os.path.join(BASE_DIR, ".test_real_cache"))


@pytest.fixture
def nbp_mock():
    class _MockNBP(NBP):
        def load_cache(self):
            pass

        def get_nbp_day_before(self, currency: str, date: datetime):
            return 2

        def save_cache(self):
            pass

    return _MockNBP()


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
        ["10", "", "XYZ", "ISIN", "TRADE", "2020-02-01 00:00:00", "-10", "XYZ", "", ""],
        ["11", "", "XYZ", "None", "TRADE", "2020-02-01 00:00:00", "100", "USD", "", ""],
        ["12", "", "XYZ", "None", "COMMISSION", "2020-02-01 00:00:00", "1", "USD", "", ""],

        ["13", "", "QQQ", "None", "DIVIDEND", "2020-01-01 00:00:00", "60.10", "USD", "", ""],
        ["14", "", "QQQ", "None", "TAX", "2020-01-01 00:00:00", "-2.2", "USD", "", ""],
    ]

    account._parse_transaction_log(data)
    account.init_cash_flow(nbp_mock)
    return account


@pytest.fixture
def mintos_account(nbp_mock):
    account = MintosAccount()
    data = [
        ["2020-01-01 00:00:01", "1", "Loan 21157138-01 - interest received", "2.5E-5", "", "EUR"],
        ["2020-01-01 00:00:02", "1", "Loan 21157138-01 - late fees received", "1.25E-5", "", "EUR"],
        ["2020-01-01 00:00:07", "1", "Loan 21157138-01 - late fees received", "2.85E-3", "", "EUR"],
        ["2020-01-01 00:00:03", "1", "Loan 21157138-01 - interest received", "20.000000", "", "EUR"],
        ["2020-01-01 00:00:04", "1", "Loan 21157138-01 - secondary market fee", "20.000000", "", "EUR"],
        ["2020-01-01 00:00:05", "1", "Loan 21157138-01 - discount/premium for secondary market transaction", "20.000000", "", "EUR"],
    ]

    account._parse_transaction_log(data)
    account.init_cash_flow(nbp_mock)
    return account