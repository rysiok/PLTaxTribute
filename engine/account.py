import csv
from abc import ABCMeta, abstractmethod
from typing import List

from engine.NBP import NBP
from engine.utils import ParseError


class AccountBase(metaclass=ABCMeta):
    def __init__(self, warning_handler=None):
        self.cash_flows = {}
        self.transaction_log = {}

        def _no_warn(e):
            pass

        self._warning_handler = warning_handler if warning_handler else _no_warn

    @staticmethod
    def load_csv_file(file, encoding, delimiter):
        with open(file, newline='', encoding=encoding) as csv_file:
            reader = csv.reader(csv_file, delimiter=delimiter)
            next(reader, None)  # skip header
            return [row for row in reader]

    def _load_transaction_log(self, file, encoding, delimiter, sort_by=None):
        rows = AccountBase.load_csv_file(file, encoding, delimiter)
        self._parse_transaction_log(rows, sort_by)

    def _parse_transaction_log(self, rows, sort_by=None):
        if sort_by:
            rows.sort(key=sort_by)
        for row in rows:
            try:
                self._parse(row)
            except ParseError as e:
                self._warning_handler(e)

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
