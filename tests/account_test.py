import os

from engine.account import AccountBase
from engine.utils import ParseError
from tests import BASE_DIR


class TestAccount(AccountBase):
    tr_log = 0

    def _parse(self, row):
        if row == 666:
            raise ParseError("666")
        self.transaction_log[str(row)] = row

    def load_transaction_log(self, file):
        self.tr_log += 1

    def _load_cash_flow(self, nbp):
        pass


def test_load_transaction_logs():
    account = TestAccount()
    account.load_transaction_logs(os.path.join(BASE_DIR, "multi"))
    assert account.tr_log == 2


def test_load_csv_file():
    assert len(AccountBase.load_csv_file(os.path.join(BASE_DIR, "account_16.csv"), "utf=16", '\t')) == 3
    assert len(AccountBase.load_csv_file(os.path.join(BASE_DIR, "account_8.csv"), "ASCII", ',')) == 3


def test_parse_transaction_log():
    rows = [1, 2, 3]
    account = TestAccount()
    account._parse_transaction_log(rows)
    assert account.transaction_log[str(rows[2])] == rows[2]


def test_parse_transaction_log_sort():
    data = [3, 1, 5]

    account = TestAccount()
    account._parse_transaction_log(data, lambda x: x)
    assert list(account.transaction_log.values()) == sorted(data)


def test_parse_transaction_log_warning_handler():
    message = ""
    data = [1, 2, 3, 666]

    def handler(e):
        nonlocal message
        message = e

    account = TestAccount(handler)
    account._parse_transaction_log(data)
    assert str(message) == "666"
