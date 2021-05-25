import os
from datetime import datetime

import pytest

from engine.NBP import NBP
from engine.exante import ExanteAccount
from tests import BASE_DIR

test_cache_file = os.path.join(BASE_DIR, ".test_cache")
transactions_file = os.path.join(BASE_DIR, "exante.csv")


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
        def get_nbp_day_before(self, currency: str, date: datetime):
            return 2

    return _MockNBP()


@pytest.fixture
def account(nbp_mock):
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
