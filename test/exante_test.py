import os
from datetime import datetime
from decimal import Decimal

import pytest

from engine.NBP import NBP
from engine.exante import ExanteAccount

test_cache_file = ".test_cache"
transactions_file = r"exante.csv"


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


@pytest.fixture
def account_real(capfd, nbp_real):
    account = ExanteAccount()
    account.load_transaction_log(transactions_file)
    account.init_cash_flow(nbp_real)
    return account, capfd.readouterr().out


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
    account = ExanteAccount()
    account.load_transaction_log(transactions_file)
    captured = capfd.readouterr()
    assert "Unsupported transaction type AUTOCONVERSION." in captured.out


def test_init_cash_flow(account_real):
    account, out = account_real
    cf = account.cash_flows
    assert "No BUY transactions for symbol: TestNoBuyFXF.ARCA." in out
    assert len(cf) == 5
    assert len(cf['TLT.NASDAQ']) == 2
    assert len(cf['FXF.ARCA']) == 16
    assert len(cf['PSLV.ARCA']) == 4
    assert len(cf['GDXJ.ARCA']) == 2
    assert len(cf['ZSIL.SIX']) == 0


def test_get_foreign(account_real):
    account, _ = account_real
    t = account.get_foreign()[1:]  # skip header
    assert len(t) == 2
    assert t[0][0] == 'FXF.ARCA', "symbol"
    assert t[0][2] == Decimal("29726.63"), "income"
    assert t[0][3] == Decimal("29546.73"), "cost"
    assert t[0][4] == Decimal("179.90"), "P/L"
    assert t[0][5] == Decimal("12.04"), "commission"
    assert t[0][2] - t[0][3] == Decimal("179.90"), "P/L"

    assert t[1][0] == 'PSLV.ARCA', "symbol"
    assert t[1][2] == Decimal("9.96"), "income"
    assert t[1][3] == Decimal("7.12"), "cost"
    assert t[1][4] == Decimal("2.84"), "P/L"
    assert t[1][5] == Decimal("0.04"), "commission"
    assert t[1][2] - t[1][3] == Decimal("2.84"), "P/L"


def test_get_pln(account_real):
    account, _ = account_real
    t = account.get_pln()[1:]  # skip header
    assert len(t) == 4
    assert t[0][0] == 'FXF.ARCA', "symbol"
    assert t[0][1] == Decimal("113845.99"), "income"
    assert t[0][2] == Decimal("115924.64"), "cost"
    assert t[0][3] == Decimal("-2078.65"), "P/L"
    assert t[0][4] == Decimal("46.66"), "commission"
    assert t[0][1] - t[0][2] == t[0][3], "P/L"

    assert t[1][0] == 'PSLV.ARCA', "symbol"
    assert t[1][1] == Decimal("37.09"), "income"
    assert t[1][2] == Decimal("28.16"), "cost"
    assert t[1][3] == Decimal("8.93"), "P/L"
    assert t[1][4] == Decimal("0.14"), "commission"
    assert t[1][1] - t[1][2] == t[1][3], "P/L"

    assert t[3][0] == 'TOTAL', "symbol"
    assert t[3][1] == Decimal("113883.08"), "income"
    assert t[3][2] == Decimal("115952.80"), "cost"
    assert t[3][3] == Decimal("-2069.72"), "P/L"
    assert t[3][1] - t[3][2] == t[3][3], "P/L"

    assert t[0][1] + t[1][1] == Decimal("113883.08"), "income"
    assert t[0][2] + t[1][2] == Decimal("115952.80"), "cost"
    assert t[0][3] + t[1][3] == Decimal("-2069.72"), "P/L"


def test_get_pln_total(account_real):
    account, _ = account_real
    t = account.get_pln_total()[1:]  # skip header
    assert len(t) == 1
    assert t[0][0] == Decimal("113883.08"), "income"
    assert t[0][1] == Decimal("115952.80"), "cost"
    assert t[0][2] == Decimal("-2069.72"), "P/L"
    assert t[0][0] - t[0][1] == t[0][2], "P/L"


def test_dividends(account_real):
    account, _ = account_real
    t = account.get_dividends()[1:]  # skip header
    assert len(t) == 2
    assert t[0][0] == 'GDXJ.ARCA', "symbol"
    assert t[0][2] == Decimal("3.42"), "income"
    assert t[0][3] == Decimal("0.52"), "tax"
    assert t[0][4] == Decimal("15"), "%"
    assert round(t[0][3] / t[0][2] * 100) == Decimal("15"), "%"

    assert t[1][0] == 'TLT.NASDAQ', "symbol"
    assert t[1][2] == Decimal("15.57"), "income"
    assert t[1][3] == Decimal("2.34"), "tax"
    assert t[1][4] == Decimal("15"), "%"
    assert round(t[1][3] / t[1][2] * 100) == Decimal("15"), "%"


def test_dividends_pln(account_real):
    account, _ = account_real
    t = account.get_dividends_pln()[1:]  # skip header
    assert len(t) == 1
    assert t[0][0] == Decimal("68.99"), "income"
    assert t[0][1] == Decimal("10.39 "), "paid tax "
    assert t[0][2] == Decimal("15"), "%"
    assert round(t[0][1] / t[0][0] * 100) == Decimal("15"), "%"
    assert t[0][3] == Decimal("13.11"), "total to pay"
    assert t[0][4] == Decimal("3"), "left to pay"
    assert round(t[0][0] * Decimal("0.19"), 2) == Decimal("13.11"), "total to pay"
    assert round(round(t[0][0] * Decimal("0.19"), 2) - t[0][1]) == Decimal("3"), "left to pay"
