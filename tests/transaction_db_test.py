from decimal import Decimal

from database.transaction_db import TransactionDB


class _FakeCursor:
    def __init__(self, next_value):
        self.next_value = next_value

    def execute(self, _query, _params=None):
        return None

    def fetchone(self):
        return (self.next_value,)


class _FakeConnection:
    def __init__(self, next_value):
        self._cursor = _FakeCursor(next_value)

    def cursor(self):
        return self._cursor

    def close(self):
        return None


def test_peek_next_customer_number_formats_decimal_sequence(monkeypatch):
    monkeypatch.setattr(
        TransactionDB,
        "_get_connection",
        staticmethod(lambda: _FakeConnection(Decimal("7"))),
    )
    monkeypatch.setattr(
        TransactionDB,
        "_schema_info",
        {
            "transaction_columns": {"date", "transaction_id"},
            "item_columns": set(),
            "product_columns": {"id"},
            "tx_id_col": "transaction_id",
            "tx_date_col": "date",
            "product_pk_col": "id",
            "has_cashier_name": True,
            "item_amount_col": "subtotal",
        },
    )

    assert TransactionDB.peek_next_customer_number("Take Out") == "TO-008"
