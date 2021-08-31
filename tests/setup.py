import os
from datetime import datetime

import pytest

from engine.NBP import NBP
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


