import os
from datetime import datetime
from decimal import Decimal

import pytest

from main import NBP, Account

test_cache_file = ".test_cache"


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
    return NBP(".test_real_cache")


def test_save_load_cache(nbp: NBP):
    cache_key = "2000-01-05 GBP"
    cache_value = 7.77
    cache_decimal_value = round(Decimal(cache_value), 4)
    assert len(nbp.cache) == 0, "Should be empty"

    nbp.cache = {cache_key: cache_value}

    nbp.save_cache()
    nbp.cache = None
    nbp.load_cache()
    assert nbp.cache, "Should be not empty"
    assert nbp.cache.get(cache_key) == cache_decimal_value, f"value {cache_decimal_value} should be in cache under {cache_key}"
    assert os.path.exists(test_cache_file), "cache should be on disk"
    assert nbp.get_nbp_day_before(cache_key.split(' ')[1], datetime.fromisoformat(cache_key.split(' ')[0])) == cache_decimal_value, "Should get from cache"


def test_get_nbp_day_before(nbp: NBP):
    assert nbp.get_nbp_day_before("USD", datetime.fromisoformat("2021-04-04")) == Decimal("3.8986"), "Should be Decimal(3.8986)"
    assert nbp.cache.get("2021-04-04 USD") == Decimal("3.8986"), "Should be Decimal(3.8986) from cache"


def test_load_transaction_log(capfd, nbp):
    account = Account()
    account.load_transaction_log(r"TR.csv")
    captured = capfd.readouterr()
    assert "Unsupported transaction type. Only STOCK is supported." in captured.out
    assert "TestNoStock" in captured.out
    assert "'UNSUPPORTED'" in captured.out


def test_init_cash_flow(capfd, nbp_real):
    account = Account()
    account.load_transaction_log(r"TR.csv")
    account.init_cash_flow(nbp_real)
    cf = account.cashflows
    captured = capfd.readouterr()
    assert "No BUY transactions for symbol: TestNoBuy." in captured.out
    assert len(cf) == 5
    assert len(cf['TLT.NASDAQ']) == 0
    assert len(cf['FXF.ARCA']) == 16
    assert len(cf['PSLV.ARCA']) == 4
    assert len(cf['GDXJ.ARCA']) == 0
    assert len(cf['ZSIL.SIX']) == 0
