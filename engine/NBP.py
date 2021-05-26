from datetime import datetime, timedelta
from decimal import Decimal

import requests
import simplejson as json


class NBP:
    cache = {}

    def __init__(self, cache_file: str = ".cache"):
        self.cache_file = cache_file

    def save_cache(self):
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self.cache, f)
        except OSError:  # pragma: no cover
            pass

    def load_cache(self):
        try:
            with open(self.cache_file, "rb") as f:
                self.cache = {k: round(Decimal(v), 4) for k, v in json.load(f).items()}
        except OSError:  # pragma: no cover
            pass

    def get_nbp_day_before(self, currency: str, date: datetime):
        date = date.date()
        exchange_date = date - timedelta(days=1)

        hash = f"{date} {currency}"

        hit = self.cache.get(hash, None)
        if hit:
            return hit

        while True:
            response = requests.get(r"https://api.nbp.pl/api/exchangerates/rates/a/%s/%s?format=json" % (currency, exchange_date))
            if response.status_code == 200:
                data = round(Decimal(response.json()["rates"][0]["mid"]), 4)
                self.cache[hash] = data
                return data
            exchange_date = exchange_date - timedelta(days=1)
