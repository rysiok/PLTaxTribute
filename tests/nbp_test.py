import os
from datetime import datetime
from decimal import Decimal

import pytest

from engine.NBP import NBP
from engine.utils import ExchangeRateNotFound
from tests.setup import test_cache_file, nbp

_ = (nbp,)
del _


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


def test_exchange_rate_not_found(nbp: NBP):
    with pytest.raises(ExchangeRateNotFound):
        nbp.get_nbp_day_before("xUSD", datetime.fromisoformat("2021-04-04"))

