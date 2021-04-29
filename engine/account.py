import csv
from abc import ABCMeta, abstractmethod
from typing import List

from engine.NBP import NBP


class AccountBase(metaclass=ABCMeta):
    def __init__(self):
        self.cash_flows = {}
        self.transaction_log = {}

    def _load_transaction_log(self, file, encoding, delimiter, sort_by=None):
        with open(file, newline='', encoding=encoding) as csv_file:
            reader = csv.reader(csv_file, delimiter=delimiter)
            next(reader, None)  # skip header
            rows = [row for row in reader]
        if sort_by:
            rows.sort(key=sort_by)
        for row in rows:
            self._parse(row)

    def init_cash_flow(self, nbp=NBP()):
        nbp.load_cache()

        self._load_cash_flow(nbp)

        nbp.save_cache()

    @abstractmethod
    def load_transaction_log(self, file):
        pass

    @abstractmethod
    def _parse(self, row: List[str]):
        pass

    @abstractmethod
    def _load_cash_flow(self, nbp):
        pass
