from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from database.db import get_connection
from models.product import Product
from models.transaction import Transaction


class TransactionDB:
    _schema_checked = False
    _schema_info = None

    @staticmethod
    def _get_connection():
        conn = get_connection()
        TransactionDB._ensure_schema(conn)
        return conn

    @staticmethod
    def _get_columns(cursor, table_name):
        cursor.execute(
            """
            SELECT COLUMN_NAME
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
            """,
            (table_name,),
        )
        return {row[0] for row in cursor.fetchall()}

    @staticmethod
    def _has_column(columns, name):
        return name in columns

    @staticmethod
    def _schema():
        if not TransactionDB._schema_info:
            raise RuntimeError("TransactionDB schema was not initialized.")
        return TransactionDB._schema_info

    @staticmethod
    def _ensure_schema(conn):
        cursor = conn.cursor()

        if not TransactionDB._schema_checked:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                    setting_key VARCHAR(100) PRIMARY KEY,
                    setting_value VARCHAR(255) NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP
                )
                """
            )

            transaction_columns = TransactionDB._get_columns(cursor, "transactions")
            item_columns = TransactionDB._get_columns(cursor, "transaction_items")
            product_columns = TransactionDB._get_columns(cursor, "products")

            if TransactionDB._has_column(transaction_columns, "payment_method") and not TransactionDB._has_column(transaction_columns, "total"):
                cursor.execute(
                    "ALTER TABLE transactions ADD COLUMN total DOUBLE NULL AFTER payment_method"
                )
                transaction_columns.add("total")

            if TransactionDB._has_column(transaction_columns, "total"):
                if TransactionDB._has_column(transaction_columns, "amount_paid"):
                    cursor.execute(
                        """
                        UPDATE transactions
                        SET total = COALESCE(total, amount_paid)
                        WHERE total IS NULL
                        """
                    )
                else:
                    cursor.execute(
                        "ALTER TABLE transactions ADD COLUMN amount_paid DOUBLE NOT NULL DEFAULT 0 AFTER payment_method"
                    )
                    transaction_columns.add("amount_paid")
                    cursor.execute(
                        "UPDATE transactions SET amount_paid = COALESCE(total, 0) WHERE amount_paid IS NULL OR amount_paid = 0"
                    )

            if not TransactionDB._has_column(transaction_columns, "is_voided"):
                cursor.execute(
                    "ALTER TABLE transactions ADD COLUMN is_voided TINYINT(1) NOT NULL DEFAULT 0 AFTER amount_paid"
                )
                transaction_columns.add("is_voided")

            if not TransactionDB._has_column(transaction_columns, "service_mode"):
                cursor.execute(
                    "ALTER TABLE transactions ADD COLUMN service_mode VARCHAR(20) NULL AFTER payment_method"
                )
                transaction_columns.add("service_mode")

            if not TransactionDB._has_column(transaction_columns, "order_source"):
                cursor.execute(
                    "ALTER TABLE transactions ADD COLUMN order_source VARCHAR(30) NULL AFTER service_mode"
                )
                transaction_columns.add("order_source")

            if not TransactionDB._has_column(transaction_columns, "customer_number"):
                cursor.execute(
                    "ALTER TABLE transactions ADD COLUMN customer_number VARCHAR(20) NULL AFTER order_source"
                )
                transaction_columns.add("customer_number")

            if not TransactionDB._has_column(transaction_columns, "pickup_date_from"):
                cursor.execute(
                    "ALTER TABLE transactions ADD COLUMN pickup_date_from DATE NULL AFTER customer_number"
                )
                transaction_columns.add("pickup_date_from")

            if not TransactionDB._has_column(transaction_columns, "pickup_date_to"):
                cursor.execute(
                    "ALTER TABLE transactions ADD COLUMN pickup_date_to DATE NULL AFTER pickup_date_from"
                )
                transaction_columns.add("pickup_date_to")

            if not TransactionDB._has_column(transaction_columns, "online_order_status"):
                cursor.execute(
                    "ALTER TABLE transactions ADD COLUMN online_order_status VARCHAR(20) NULL AFTER pickup_date_to"
                )
                transaction_columns.add("online_order_status")

            if not TransactionDB._has_column(transaction_columns, "accepted_at"):
                cursor.execute(
                    "ALTER TABLE transactions ADD COLUMN accepted_at DATETIME NULL AFTER online_order_status"
                )
                transaction_columns.add("accepted_at")

            if not TransactionDB._has_column(transaction_columns, "processed_at"):
                cursor.execute(
                    "ALTER TABLE transactions ADD COLUMN processed_at DATETIME NULL AFTER accepted_at"
                )
                transaction_columns.add("processed_at")

            if not TransactionDB._has_column(transaction_columns, "date") and TransactionDB._has_column(transaction_columns, "transaction_date"):
                cursor.execute(
                    "ALTER TABLE transactions ADD COLUMN date DATETIME NULL AFTER processed_at"
                )
                transaction_columns.add("date")
                cursor.execute(
                    "UPDATE transactions SET date = transaction_date WHERE date IS NULL"
                )

            if not TransactionDB._has_column(transaction_columns, "transaction_id") and TransactionDB._has_column(transaction_columns, "id"):
                cursor.execute(
                    "ALTER TABLE transactions ADD COLUMN transaction_id INT NULL AFTER date"
                )
                transaction_columns.add("transaction_id")
                cursor.execute(
                    "UPDATE transactions SET transaction_id = id WHERE transaction_id IS NULL"
                )

            if not TransactionDB._has_column(item_columns, "subtotal"):
                cursor.execute(
                    "ALTER TABLE transaction_items ADD COLUMN subtotal DOUBLE NULL AFTER price"
                )
                item_columns.add("subtotal")
                if TransactionDB._has_column(item_columns, "price"):
                    cursor.execute(
                        "UPDATE transaction_items SET subtotal = price WHERE subtotal IS NULL"
                    )

            if not TransactionDB._has_column(item_columns, "product_name"):
                cursor.execute(
                    "ALTER TABLE transaction_items ADD COLUMN product_name VARCHAR(255) NULL AFTER subtotal"
                )
                item_columns.add("product_name")

            if TransactionDB._has_column(item_columns, "product_name") and TransactionDB._has_column(item_columns, "product_id"):
                product_join_id = "product_id" if TransactionDB._has_column(product_columns, "product_id") else "id"
                cursor.execute(
                    f"""
                    UPDATE transaction_items ti
                    LEFT JOIN products p ON ti.product_id = p.{product_join_id}
                    SET ti.product_name = COALESCE(ti.product_name, p.name)
                    WHERE ti.product_name IS NULL OR ti.product_name = ''
                    """
                )

            TransactionDB._ensure_index(
                cursor,
                "transactions",
                "idx_transactions_voided_date",
                "CREATE INDEX idx_transactions_voided_date ON transactions (is_voided, date)",
            )
            TransactionDB._ensure_index(
                cursor,
                "transactions",
                "idx_transactions_date_id",
                "CREATE INDEX idx_transactions_date_id ON transactions (date, transaction_id)",
            )
            TransactionDB._ensure_index(
                cursor,
                "transaction_items",
                "idx_transaction_items_transaction_id",
                "CREATE INDEX idx_transaction_items_transaction_id ON transaction_items (transaction_id)",
            )
            TransactionDB._ensure_index(
                cursor,
                "transaction_items",
                "idx_transaction_items_product_id",
                "CREATE INDEX idx_transaction_items_product_id ON transaction_items (product_id)",
            )
            if TransactionDB._has_column(product_columns, "category"):
                TransactionDB._ensure_index(
                    cursor,
                    "products",
                    "idx_products_category",
                    "CREATE INDEX idx_products_category ON products (category)",
                )
            TransactionDB._ensure_index(
                cursor,
                "transactions",
                "idx_transactions_service_mode_date",
                "CREATE INDEX idx_transactions_service_mode_date ON transactions (service_mode, date)",
            )
            TransactionDB._ensure_index(
                cursor,
                "transactions",
                "idx_transactions_source_status_date",
                "CREATE INDEX idx_transactions_source_status_date ON transactions (order_source, online_order_status, date)",
            )
            cursor.execute(
                """
                INSERT IGNORE INTO app_settings (setting_key, setting_value)
                VALUES ('online_orders_accepting', '1')
                """
            )
            cursor.execute(
                """
                UPDATE transactions
                SET online_order_status = CASE
                    WHEN is_voided = 1 THEN 'voided'
                    ELSE 'processed'
                END
                WHERE COALESCE(order_source, 'Walk-In') = 'Online Orders'
                  AND COALESCE(online_order_status, '') = ''
                """
            )
            conn.commit()
            TransactionDB._schema_checked = True

        transaction_columns = TransactionDB._get_columns(cursor, "transactions")
        item_columns = TransactionDB._get_columns(cursor, "transaction_items")
        product_columns = TransactionDB._get_columns(cursor, "products")

        if "id" in transaction_columns:
            tx_id_col = "id"
        else:
            tx_id_col = "transaction_id"
        tx_date_col = "date" if "date" in transaction_columns else "transaction_date"
        product_pk_col = "product_id" if "product_id" in product_columns else "id"
        has_cashier_name = "cashier_name" in transaction_columns
        item_amount_col = "subtotal" if "subtotal" in item_columns else "price"

        TransactionDB._schema_info = {
            "transaction_columns": transaction_columns,
            "item_columns": item_columns,
            "product_columns": product_columns,
            "tx_id_col": tx_id_col,
            "tx_date_col": tx_date_col,
            "product_pk_col": product_pk_col,
            "has_cashier_name": has_cashier_name,
            "item_amount_col": item_amount_col,
        }

    @staticmethod
    def _ensure_index(cursor, table_name, index_name, create_sql):
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
              AND INDEX_NAME = %s
            """,
            (table_name, index_name),
        )
        if cursor.fetchone()[0] == 0:
            try:
                cursor.execute(create_sql)
            except Exception as exc:
                message = str(exc)
                if "Duplicate key name" not in message and "Duplicate" not in message:
                    raise

    @staticmethod
    def _transaction_timestamp(value):
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(value, date):
            return f"{value.isoformat()} {datetime.now().strftime('%H:%M:%S')}"
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def _normalize_category(category):
        if category is None:
            return None
        normalized = str(category).strip()
        if not normalized or normalized.lower() == "all categories":
            return None
        return normalized

    @staticmethod
    def _coerce_bucket_date(value):
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str) and value:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        return value

    @staticmethod
    def _trend_bucket_sql(group_by, date_expr):
        normalized = str(group_by or "day").strip().lower()
        if normalized in {"weekly", "week"}:
            return f"DATE_SUB(DATE({date_expr}), INTERVAL WEEKDAY(DATE({date_expr})) DAY)"
        if normalized in {"monthly", "month"}:
            return f"CAST(DATE_FORMAT(DATE({date_expr}), '%Y-%m-01') AS DATE)"
        return f"DATE({date_expr})"

    @staticmethod
    def _report_sort_order(sort_key=None, sort_direction=None):
        key = str(sort_key or "receipt").strip().lower()
        direction = "ASC" if str(sort_direction or "desc").strip().lower() == "asc" else "DESC"

        if key == "date":
            return f"date {direction}, id {direction}"
        if key == "payment":
            return f"payment_sort_value {direction}, date DESC, id DESC"
        if key == "status":
            if direction == "ASC":
                return "is_voided DESC, date DESC, id DESC"
            return "is_voided ASC, date DESC, id DESC"
        if key == "total":
            return f"total_value {direction}, date DESC, id DESC"
        return f"DATE(date) {direction}, receipt_prefix_rank ASC, receipt_sort_value {direction}, id {direction}"

    @staticmethod
    def _date_window_bounds(start_date, end_date):
        start_value = date.fromisoformat(str(start_date)) if isinstance(start_date, str) else start_date
        end_value = date.fromisoformat(str(end_date)) if isinstance(end_date, str) else end_date
        range_start = datetime.combine(start_value, datetime.min.time())
        range_end = datetime.combine(end_value + timedelta(days=1), datetime.min.time())
        return range_start, range_end

    @staticmethod
    def _tx_id(alias=""):
        prefix = f"{alias}." if alias else ""
        return prefix + TransactionDB._schema()["tx_id_col"]

    @staticmethod
    def _tx_date(alias=""):
        prefix = f"{alias}." if alias else ""
        return prefix + TransactionDB._schema()["tx_date_col"]

    @staticmethod
    def _product_pk(alias=""):
        prefix = f"{alias}." if alias else ""
        return prefix + TransactionDB._schema()["product_pk_col"]

    @staticmethod
    def _item_amount(alias=""):
        prefix = f"{alias}." if alias else ""
        return prefix + TransactionDB._schema()["item_amount_col"]

    @staticmethod
    def _cashier_select(alias=""):
        schema = TransactionDB._schema()
        if schema["has_cashier_name"]:
            prefix = f"{alias}." if alias else ""
            return f"{prefix}cashier_name"
        return "''"

    @staticmethod
    def get_transaction_date_bounds():
        conn = TransactionDB._get_connection()
        cursor = conn.cursor()
        try:
            date_col = TransactionDB._tx_date()
            completed_filter = TransactionDB._completed_sales_filter()
            cursor.execute(
                f"""
                SELECT MIN(DATE({date_col})), MAX(DATE({date_col}))
                FROM transactions
                WHERE is_voided = 0
                  AND {completed_filter}
                """
            )
            row = cursor.fetchone() or (None, None)
            return row[0], row[1]
        finally:
            conn.close()

    @staticmethod
    def _completed_sales_filter(alias=""):
        prefix = f"{alias}." if alias else ""
        return (
            f"(COALESCE({prefix}order_source, 'Walk-In') <> 'Online Orders' "
            f"OR COALESCE({prefix}online_order_status, 'processed') IN ('processed', 'voided'))"
        )

    @staticmethod
    def _select_transactions_sql(where_clause="", include_pending_online=False):
        tx_id = TransactionDB._tx_id()
        tx_date = TransactionDB._tx_date()
        cashier_sql = TransactionDB._cashier_select()
        query = f"""
            SELECT
                {tx_id} AS id,
                {cashier_sql} AS cashier_name,
                {tx_date} AS date,
                payment_method,
                service_mode,
                order_source,
                customer_number,
                pickup_date_from,
                pickup_date_to,
                online_order_status,
                accepted_at,
                processed_at,
                total,
                amount_paid,
                is_voided
            FROM transactions
        """
        clauses = []
        if where_clause:
            clauses.append(where_clause.strip())
        if not include_pending_online:
            pending_filter = TransactionDB._completed_sales_filter()
            if clauses:
                clauses.append(f"AND {pending_filter}")
            else:
                clauses.append(f"WHERE {pending_filter}")
        if clauses:
            query += " " + " ".join(clauses)
        query += f" ORDER BY {tx_id} DESC"
        return query

    @staticmethod
    def _service_mode_prefix(service_mode, order_source="Walk-In"):
        if str(order_source or "Walk-In").strip().lower() == "online orders":
            return "ON"
        normalized = str(service_mode or "Take Out").strip().lower()
        return "DI" if normalized == "dine in" else "TO"

    @staticmethod
    def peek_next_customer_number(service_mode, on_date=None, order_source="Walk-In"):
        conn = TransactionDB._get_connection()
        cursor = conn.cursor()
        try:
            target_date = on_date or date.today()
            range_start, range_end = TransactionDB._date_window_bounds(target_date, target_date)
            tx_date = TransactionDB._tx_date()
            prefix = TransactionDB._service_mode_prefix(service_mode, order_source=order_source)
            cursor.execute(
                f"""
                SELECT COALESCE(MAX(CAST(SUBSTRING_INDEX(customer_number, '-', -1) AS UNSIGNED)), 0)
                FROM transactions
                WHERE service_mode = %s
                  AND order_source = %s
                  AND {tx_date} >= %s
                  AND {tx_date} < %s
                  AND customer_number LIKE %s
                  AND customer_number REGEXP '-[0-9]+$'
                """,
                (service_mode, order_source, range_start, range_end, f"{prefix}-%"),
            )
            next_number = int(cursor.fetchone()[0] or 0) + 1
            return f"{prefix}-{next_number:03d}"
        finally:
            conn.close()

    @staticmethod
    def save_transaction(transaction):
        conn = TransactionDB._get_connection()
        cursor = conn.cursor()
        schema = TransactionDB._schema()

        try:
            tx_total = transaction.get_total()
            raw_amount_paid = transaction.amount_paid
            if raw_amount_paid in (None, ""):
                tx_amount_paid = tx_total
            else:
                tx_amount_paid = Decimal(str(raw_amount_paid))
            tx_date = TransactionDB._transaction_timestamp(transaction.date)
            tx_day = tx_date[:10]
            order_source = transaction.order_source or "Walk-In"
            if order_source == "Online Orders":
                service_mode = "Online Orders"
            else:
                service_mode = transaction.service_mode or "Take Out"
            pickup_date_from = transaction.pickup_date_from
            pickup_date_to = transaction.pickup_date_to
            online_order_status = getattr(transaction, "online_order_status", None)
            accepted_at = getattr(transaction, "accepted_at", None)
            processed_at = getattr(transaction, "processed_at", None)
            if order_source == "Online Orders":
                online_order_status = online_order_status or "pending"
                if online_order_status == "accepted" and not accepted_at:
                    accepted_at = tx_date
                if online_order_status == "processed" and not processed_at:
                    processed_at = tx_date
            elif online_order_status == "processed" and not processed_at:
                processed_at = tx_date
            if transaction.customer_number:
                customer_number = transaction.customer_number
            else:
                customer_number = TransactionDB.peek_next_customer_number(
                    service_mode,
                    on_date=date.fromisoformat(tx_day),
                    order_source=order_source,
                )
                transaction.customer_number = customer_number

            columns = []
            values = []

            if schema["has_cashier_name"]:
                columns.append("cashier_name")
                values.append(transaction.cashier_name)
            if "date" in schema["transaction_columns"]:
                columns.append("date")
                values.append(tx_date)
            if "transaction_date" in schema["transaction_columns"]:
                columns.append("transaction_date")
                values.append(tx_date)
            columns.extend(
                [
                    "payment_method",
                    "service_mode",
                    "order_source",
                    "customer_number",
                    "pickup_date_from",
                    "pickup_date_to",
                    "online_order_status",
                    "accepted_at",
                    "processed_at",
                    "total",
                    "amount_paid",
                    "is_voided",
                ]
            )
            values.extend(
                [
                    transaction.payment_method,
                    service_mode,
                    order_source,
                    customer_number,
                    pickup_date_from,
                    pickup_date_to,
                    online_order_status,
                    accepted_at,
                    processed_at,
                    float(tx_total),
                    float(tx_amount_paid),
                    int(bool(transaction.is_voided)),
                ]
            )

            placeholders = ", ".join(["%s"] * len(columns))
            cursor.execute(
                f"INSERT INTO transactions ({', '.join(columns)}) VALUES ({placeholders})",
                tuple(values),
            )
            inserted_pk = cursor.lastrowid

            actual_transaction_id = inserted_pk
            if "transaction_id" in schema["transaction_columns"] and "id" in schema["transaction_columns"]:
                cursor.execute(
                    "UPDATE transactions SET transaction_id = %s WHERE id = %s AND (transaction_id IS NULL OR transaction_id = 0)",
                    (inserted_pk, inserted_pk),
                )

            item_query = """
                INSERT INTO transaction_items
                    (transaction_id, product_id, product_name, quantity, price, subtotal)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            for item in transaction.items:
                quantity = int(item["quantity"] or 0)
                subtotal = Decimal(str(item["subtotal"]))
                unit_price = (
                    subtotal / Decimal(str(quantity))
                    if quantity
                    else Decimal(str(item["product"].price))
                )
                cursor.execute(
                    item_query,
                    (
                        actual_transaction_id,
                        item["product"].product_id,
                        item["product"].name,
                        quantity,
                        float(unit_price),
                        float(subtotal),
                    ),
                )

            conn.commit()
            transaction.transaction_id = actual_transaction_id
            transaction.date = tx_date
            transaction.amount_paid = tx_amount_paid
            transaction.recorded_total = tx_total
            transaction.service_mode = service_mode
            transaction.order_source = order_source
            transaction.online_order_status = online_order_status
            transaction.accepted_at = accepted_at
            transaction.processed_at = processed_at
            return actual_transaction_id
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def accept_online_order(transaction_id, accepted_at=None):
        conn = TransactionDB._get_connection()
        cursor = conn.cursor()
        try:
            tx_id = TransactionDB._tx_id()
            accepted_value = accepted_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                f"""
                UPDATE transactions
                SET online_order_status = 'accepted',
                    accepted_at = %s
                WHERE {tx_id} = %s
                  AND order_source = 'Online Orders'
                  AND COALESCE(online_order_status, 'pending') = 'pending'
                """,
                (accepted_value, transaction_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Pending online order #{transaction_id} was not found.")
            conn.commit()
            return accepted_value
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def accept_all_pending_online_orders(accepted_at=None):
        conn = TransactionDB._get_connection()
        cursor = conn.cursor()
        try:
            accepted_value = accepted_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                """
                UPDATE transactions
                SET online_order_status = 'accepted',
                    accepted_at = %s
                WHERE order_source = 'Online Orders'
                  AND COALESCE(online_order_status, 'pending') = 'pending'
                """,
                (accepted_value,),
            )
            accepted_count = int(cursor.rowcount or 0)
            conn.commit()
            return accepted_count, accepted_value
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def complete_online_order(
        transaction_id,
        cashier_name,
        payment_method,
        amount_paid,
        pickup_date_from=None,
        pickup_date_to=None,
        processed_at=None,
    ):
        conn = TransactionDB._get_connection()
        cursor = conn.cursor(dictionary=True)
        schema = TransactionDB._schema()
        tx_id = TransactionDB._tx_id()
        try:
            processed_value = processed_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                f"""
                SELECT
                    {tx_id} AS id,
                    order_source,
                    COALESCE(online_order_status, 'pending') AS online_order_status
                FROM transactions
                WHERE {tx_id} = %s
                LIMIT 1
                """,
                (transaction_id,),
            )
            current_row = cursor.fetchone()
            if not current_row:
                raise ValueError(f"Online order #{transaction_id} was not found.")
            if str(current_row.get("order_source") or "").strip() != "Online Orders":
                raise ValueError(f"Transaction #{transaction_id} is not an online order.")
            if str(current_row.get("online_order_status") or "").strip().lower() != "accepted":
                raise ValueError(f"Online order #{transaction_id} must be accepted before checkout.")

            set_parts = []
            params = []
            if schema["has_cashier_name"]:
                set_parts.append("cashier_name = %s")
                params.append(cashier_name)
            set_parts.extend(
                [
                    "payment_method = %s",
                    "amount_paid = %s",
                    "pickup_date_from = %s",
                    "pickup_date_to = %s",
                    "accepted_at = COALESCE(accepted_at, %s)",
                    "online_order_status = 'processed'",
                    "processed_at = %s",
                ]
            )
            params.extend(
                [
                    payment_method,
                    float(Decimal(str(amount_paid or 0))),
                    pickup_date_from,
                    pickup_date_to,
                    processed_value,
                    processed_value,
                    transaction_id,
                ]
            )
            cursor.execute(
                f"""
                UPDATE transactions
                SET {', '.join(set_parts)}
                WHERE {tx_id} = %s
                  AND order_source = 'Online Orders'
                  AND COALESCE(online_order_status, 'pending') = 'accepted'
                """,
                tuple(params),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"Online order #{transaction_id} could not be completed.")
            conn.commit()
            return processed_value
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def get_online_orders_accepting():
        conn = TransactionDB._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT setting_value FROM app_settings WHERE setting_key = %s",
                ("online_orders_accepting",),
            )
            row = cursor.fetchone()
            if not row:
                return True
            return str(row[0]).strip().lower() not in {"0", "false", "off", "no"}
        finally:
            conn.close()

    @staticmethod
    def set_online_orders_accepting(is_accepting):
        conn = TransactionDB._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO app_settings (setting_key, setting_value)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value)
                """,
                ("online_orders_accepting", "1" if is_accepting else "0"),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _fetch_items_for_ids(cursor, tx_ids):
        if not tx_ids:
            return {}

        schema = TransactionDB._schema()
        placeholders = ",".join(["%s"] * len(tx_ids))
        amount_expr = f"COALESCE(ti.subtotal, ti.price)" if "price" in schema["item_columns"] else "ti.subtotal"
        product_name_expr = (
            "COALESCE(ti.product_name, p.name, 'Unknown Product')"
            if "product_name" in schema["item_columns"]
            else "COALESCE(p.name, 'Unknown Product')"
        )
        cursor.execute(
            f"""
            SELECT
                ti.transaction_id,
                ti.product_id,
                {product_name_expr} AS product_name,
                ti.quantity,
                {amount_expr} AS subtotal,
                p.name AS current_name,
                p.category,
                p.price AS current_price,
                p.shelf_life_days
            FROM transaction_items ti
            LEFT JOIN products p ON ti.product_id = p.{schema['product_pk_col']}
            WHERE ti.transaction_id IN ({placeholders})
            ORDER BY ti.id ASC
            """,
            tx_ids,
        )
        rows = cursor.fetchall()

        items_map = defaultdict(list)
        for row in rows:
            quantity = row["quantity"] or 0
            subtotal = Decimal(str(row["subtotal"] or 0))
            saved_product_name = row["product_name"] or row["current_name"] or "Unknown Product"
            if quantity:
                saved_unit_price = subtotal / Decimal(str(quantity))
            else:
                saved_unit_price = Decimal("0.00")
            current_unit_price = (
                Decimal(str(row["current_price"]))
                if row["current_price"] is not None
                else saved_unit_price
            )

            product = Product(
                row["product_id"] or 0,
                row["current_name"] or saved_product_name,
                row["category"] or "Unknown",
                current_unit_price,
                row["shelf_life_days"] or 0,
            )
            items_map[row["transaction_id"]].append(
                {
                    "product": product,
                    "quantity": quantity,
                    "subtotal": subtotal,
                    "saved_product_name": saved_product_name,
                    "saved_unit_price": saved_unit_price,
                }
            )
        return items_map

    @staticmethod
    def _build_transactions(rows, cursor, include_items=True):
        if not rows:
            return []

        items_map = {}
        if include_items:
            tx_ids = [row["id"] for row in rows]
            items_map = TransactionDB._fetch_items_for_ids(cursor, tx_ids)

        transactions = []
        for row in rows:
            transaction = Transaction(row["id"], cashier_name=row.get("cashier_name") or "")
            transaction.date = row["date"]
            transaction.payment_method = row.get("payment_method")
            transaction.service_mode = row.get("service_mode") or "Take Out"
            transaction.order_source = row.get("order_source") or "Walk-In"
            transaction.customer_number = row.get("customer_number")
            transaction.pickup_date_from = row.get("pickup_date_from")
            transaction.pickup_date_to = row.get("pickup_date_to")
            transaction.online_order_status = row.get("online_order_status")
            transaction.accepted_at = row.get("accepted_at")
            transaction.processed_at = row.get("processed_at")
            transaction.amount_paid = Decimal(str(row.get("amount_paid") or 0))
            transaction.is_voided = bool(row.get("is_voided"))
            transaction.items = items_map.get(row["id"], [])

            total_value = row.get("total")
            if total_value is None:
                total_value = transaction.amount_paid
            transaction.recorded_total = Decimal(str(total_value))
            transactions.append(transaction)
        return transactions

    @staticmethod
    def get_all_transactions(limit=None, offset=0, include_items=True):
        conn = TransactionDB._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            query = TransactionDB._select_transactions_sql()
            params = []
            if limit is not None:
                query += " LIMIT %s OFFSET %s"
                params = [limit, offset]

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return TransactionDB._build_transactions(rows, cursor, include_items=include_items)
        finally:
            conn.close()

    @staticmethod
    def get_transaction_by_id(transaction_id, include_items=True):
        conn = TransactionDB._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            query = TransactionDB._select_transactions_sql(
                f"WHERE {TransactionDB._tx_id()} = %s",
                include_pending_online=True,
            )
            cursor.execute(query, (transaction_id,))
            rows = cursor.fetchall()
            transactions = TransactionDB._build_transactions(rows, cursor, include_items=include_items)
            return transactions[0] if transactions else None
        finally:
            conn.close()

    @staticmethod
    def get_transaction_count():
        conn = TransactionDB._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM transactions WHERE " + TransactionDB._completed_sales_filter()
            )
            return cursor.fetchone()[0]
        finally:
            conn.close()

    @staticmethod
    def get_today_revenue():
        conn = TransactionDB._get_connection()
        cursor = conn.cursor()
        try:
            range_start, range_end = TransactionDB._date_window_bounds(date.today(), date.today())
            completed_filter = TransactionDB._completed_sales_filter()
            tx_date = TransactionDB._tx_date()
            cursor.execute(
                f"""
                SELECT COALESCE(SUM(COALESCE(total, amount_paid)), 0)
                FROM transactions
                WHERE is_voided = 0
                  AND {tx_date} >= %s
                  AND {tx_date} < %s
                  AND {completed_filter}
                """,
                (range_start, range_end),
            )
            result = cursor.fetchone()[0]
            return Decimal(str(result))
        finally:
            conn.close()

    @staticmethod
    def get_transactions_by_date(filter_date, limit=None, offset=0, include_items=True):
        return TransactionDB.get_transactions_by_range(
            filter_date,
            filter_date,
            limit=limit,
            offset=offset,
            include_items=include_items,
        )

    @staticmethod
    def get_transactions_by_range(start_date, end_date, limit=None, offset=0, include_items=True):
        conn = TransactionDB._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            range_start, range_end = TransactionDB._date_window_bounds(start_date, end_date)
            tx_date = TransactionDB._tx_date()
            query = TransactionDB._select_transactions_sql(
                f"WHERE {tx_date} >= %s AND {tx_date} < %s"
            )
            params = [range_start, range_end]
            if limit is not None:
                query += " LIMIT %s OFFSET %s"
                params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return TransactionDB._build_transactions(rows, cursor, include_items=include_items)
        finally:
            conn.close()

    @staticmethod
    def get_recent_transactions(limit=8, include_items=False):
        return TransactionDB.get_all_transactions(limit=limit, include_items=include_items)

    @staticmethod
    def get_transactions_by_source(
        order_source,
        start_date=None,
        end_date=None,
        limit=40,
        include_items=True,
        statuses=None,
    ):
        conn = TransactionDB._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            tx_date = TransactionDB._tx_date()
            filters = ["order_source = %s"]
            params = [order_source]

            if start_date is not None:
                start_value = date.fromisoformat(str(start_date)) if isinstance(start_date, str) else start_date
                filters.append(f"COALESCE(pickup_date_from, DATE({tx_date})) >= %s")
                params.append(start_value)

            if end_date is not None:
                end_value = date.fromisoformat(str(end_date)) if isinstance(end_date, str) else end_date
                filters.append(f"COALESCE(pickup_date_to, pickup_date_from, DATE({tx_date})) <= %s")
                params.append(end_value)

            if statuses:
                placeholders = ", ".join(["%s"] * len(statuses))
                filters.append(f"COALESCE(online_order_status, 'processed') IN ({placeholders})")
                params.extend(statuses)

            where_clause = "WHERE " + " AND ".join(filters)
            query = TransactionDB._select_transactions_sql(
                where_clause,
                include_pending_online=True,
            ) + " LIMIT %s"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return TransactionDB._build_transactions(rows, cursor, include_items=include_items)
        finally:
            conn.close()

    @staticmethod
    def get_pending_online_orders(limit=60, include_items=True):
        return TransactionDB.get_transactions_by_source(
            "Online Orders",
            limit=limit,
            include_items=include_items,
            statuses=["pending"],
        )

    @staticmethod
    def get_accepted_online_orders(limit=60, include_items=True):
        return TransactionDB.get_transactions_by_source(
            "Online Orders",
            limit=limit,
            include_items=include_items,
            statuses=["accepted"],
        )

    @staticmethod
    def get_sales_summary(start_date, end_date, category=None):
        category = TransactionDB._normalize_category(category)
        conn = TransactionDB._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            range_start, range_end = TransactionDB._date_window_bounds(start_date, end_date)
            tx_id = TransactionDB._tx_id("t")
            tx_date = TransactionDB._tx_date("t")
            completed_filter = TransactionDB._completed_sales_filter("t")
            item_amount = TransactionDB._item_amount("ti")
            product_pk = TransactionDB._product_pk("p")
            if category is None:
                cursor.execute(
                    f"""
                    SELECT
                        COUNT(*) AS transaction_count,
                        COALESCE(SUM(COALESCE(total, amount_paid)), 0) AS revenue
                    FROM transactions
                    WHERE is_voided = 0
                      AND {TransactionDB._tx_date()} >= %s
                      AND {TransactionDB._tx_date()} < %s
                      AND {TransactionDB._completed_sales_filter()}
                    """,
                    (range_start, range_end),
                )
            else:
                cursor.execute(
                    f"""
                    SELECT
                        COUNT(DISTINCT {tx_id}) AS transaction_count,
                        COALESCE(SUM({item_amount}), 0) AS revenue
                    FROM transactions t
                    JOIN transaction_items ti ON ti.transaction_id = {tx_id}
                    LEFT JOIN products p ON ti.product_id = {product_pk}
                    WHERE t.is_voided = 0
                      AND {tx_date} >= %s
                      AND {tx_date} < %s
                      AND {completed_filter}
                      AND COALESCE(NULLIF(p.category, ''), 'Uncategorized') = %s
                    """,
                    (range_start, range_end, category),
                )
            result = cursor.fetchone() or {}
            return {
                "transaction_count": result.get("transaction_count", 0) or 0,
                "revenue": Decimal(str(result.get("revenue", 0) or 0)),
            }
        finally:
            conn.close()

    @staticmethod
    def get_report_transactions(
        start_date,
        end_date,
        category=None,
        limit=None,
        offset=0,
        include_items=False,
        sort_key=None,
        sort_direction=None,
    ):
        category = TransactionDB._normalize_category(category)
        conn = TransactionDB._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            range_start, range_end = TransactionDB._date_window_bounds(start_date, end_date)
            params = [range_start, range_end]
            order_by = TransactionDB._report_sort_order(sort_key=sort_key, sort_direction=sort_direction)
            tx_id = TransactionDB._tx_id("t")
            tx_date = TransactionDB._tx_date("t")
            completed_filter = TransactionDB._completed_sales_filter("t")
            cashier_sql = TransactionDB._cashier_select("t")
            product_pk = TransactionDB._product_pk("p")
            if category is None:
                query = f"""
                    SELECT
                        {tx_id} AS id,
                        {cashier_sql} AS cashier_name,
                        {tx_date} AS date,
                        t.payment_method,
                        t.service_mode,
                        t.order_source,
                        t.customer_number,
                        t.pickup_date_from,
                        t.pickup_date_to,
                        t.online_order_status,
                        t.accepted_at,
                        t.processed_at,
                        t.total,
                        t.amount_paid,
                        t.is_voided,
                        LOWER(COALESCE(t.payment_method, '')) AS payment_sort_value,
                        COALESCE(t.total, t.amount_paid) AS total_value,
                        COALESCE(NULLIF(SUBSTRING_INDEX(t.customer_number, '-', 1), ''), '') AS receipt_prefix_value,
                        CASE COALESCE(NULLIF(SUBSTRING_INDEX(t.customer_number, '-', 1), ''), '')
                            WHEN 'TO' THEN 1
                            WHEN 'DI' THEN 2
                            WHEN 'ON' THEN 3
                            ELSE 9
                        END AS receipt_prefix_rank,
                        CASE
                            WHEN t.customer_number REGEXP '-[0-9]+$'
                            THEN CAST(SUBSTRING_INDEX(t.customer_number, '-', -1) AS UNSIGNED)
                            ELSE {tx_id}
                        END AS receipt_sort_value
                    FROM transactions t
                    WHERE {tx_date} >= %s
                      AND {tx_date} < %s
                      AND {completed_filter}
                    ORDER BY {order_by}
                """
            else:
                query = f"""
                    SELECT DISTINCT
                        {tx_id} AS id,
                        {cashier_sql} AS cashier_name,
                        {tx_date} AS date,
                        t.payment_method,
                        t.service_mode,
                        t.order_source,
                        t.customer_number,
                        t.pickup_date_from,
                        t.pickup_date_to,
                        t.online_order_status,
                        t.accepted_at,
                        t.processed_at,
                        t.total,
                        t.amount_paid,
                        t.is_voided,
                        LOWER(COALESCE(t.payment_method, '')) AS payment_sort_value,
                        COALESCE(t.total, t.amount_paid) AS total_value,
                        COALESCE(NULLIF(SUBSTRING_INDEX(t.customer_number, '-', 1), ''), '') AS receipt_prefix_value,
                        CASE COALESCE(NULLIF(SUBSTRING_INDEX(t.customer_number, '-', 1), ''), '')
                            WHEN 'TO' THEN 1
                            WHEN 'DI' THEN 2
                            WHEN 'ON' THEN 3
                            ELSE 9
                        END AS receipt_prefix_rank,
                        CASE
                            WHEN t.customer_number REGEXP '-[0-9]+$'
                            THEN CAST(SUBSTRING_INDEX(t.customer_number, '-', -1) AS UNSIGNED)
                            ELSE {tx_id}
                        END AS receipt_sort_value
                    FROM transactions t
                    JOIN transaction_items ti ON ti.transaction_id = {tx_id}
                    LEFT JOIN products p ON ti.product_id = {product_pk}
                    WHERE {tx_date} >= %s
                      AND {tx_date} < %s
                      AND {completed_filter}
                      AND COALESCE(NULLIF(p.category, ''), 'Uncategorized') = %s
                    ORDER BY {order_by}
                """
                params.append(category)

            if limit is not None:
                query += " LIMIT %s OFFSET %s"
                params.extend([limit, offset])

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return TransactionDB._build_transactions(rows, cursor, include_items=include_items)
        finally:
            conn.close()

    @staticmethod
    def get_report_transaction_count(start_date, end_date, category=None):
        category = TransactionDB._normalize_category(category)
        conn = TransactionDB._get_connection()
        cursor = conn.cursor()
        try:
            range_start, range_end = TransactionDB._date_window_bounds(start_date, end_date)
            tx_id = TransactionDB._tx_id("t")
            tx_date = TransactionDB._tx_date("t")
            completed_filter = TransactionDB._completed_sales_filter("t")
            product_pk = TransactionDB._product_pk("p")
            if category is None:
                cursor.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM transactions t
                    WHERE {tx_date} >= %s
                      AND {tx_date} < %s
                      AND {completed_filter}
                    """,
                    (range_start, range_end),
                )
            else:
                cursor.execute(
                    f"""
                    SELECT COUNT(DISTINCT {tx_id})
                    FROM transactions t
                    JOIN transaction_items ti ON ti.transaction_id = {tx_id}
                    LEFT JOIN products p ON ti.product_id = {product_pk}
                    WHERE {tx_date} >= %s
                      AND {tx_date} < %s
                      AND {completed_filter}
                      AND COALESCE(NULLIF(p.category, ''), 'Uncategorized') = %s
                    """,
                    (range_start, range_end, category),
                )
            result = cursor.fetchone()
            return int(result[0] or 0) if result else 0
        finally:
            conn.close()

    @staticmethod
    def get_sales_trend(start_date, end_date, group_by="day", category=None):
        category = TransactionDB._normalize_category(category)
        conn = TransactionDB._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            range_start, range_end = TransactionDB._date_window_bounds(start_date, end_date)
            tx_id = TransactionDB._tx_id("t")
            tx_date = TransactionDB._tx_date("t")
            bucket_sql = TransactionDB._trend_bucket_sql(group_by, tx_date)
            params = [range_start, range_end]
            completed_filter = TransactionDB._completed_sales_filter("t")
            item_amount = TransactionDB._item_amount("ti")
            product_pk = TransactionDB._product_pk("p")
            if category is None:
                query = f"""
                    SELECT
                        {bucket_sql} AS bucket_start,
                        COUNT(*) AS transaction_count,
                        COALESCE(SUM(COALESCE(t.total, t.amount_paid)), 0) AS revenue
                    FROM transactions t
                    WHERE t.is_voided = 0
                      AND {tx_date} >= %s
                      AND {tx_date} < %s
                      AND {completed_filter}
                    GROUP BY bucket_start
                    ORDER BY bucket_start ASC
                """
            else:
                query = f"""
                    SELECT
                        {bucket_sql} AS bucket_start,
                        COUNT(DISTINCT {tx_id}) AS transaction_count,
                        COALESCE(SUM({item_amount}), 0) AS revenue
                    FROM transactions t
                    JOIN transaction_items ti ON ti.transaction_id = {tx_id}
                    LEFT JOIN products p ON ti.product_id = {product_pk}
                    WHERE t.is_voided = 0
                      AND {tx_date} >= %s
                      AND {tx_date} < %s
                      AND {completed_filter}
                      AND COALESCE(NULLIF(p.category, ''), 'Uncategorized') = %s
                    GROUP BY bucket_start
                    ORDER BY bucket_start ASC
                """
                params.append(category)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [
                {
                    "bucket_start": TransactionDB._coerce_bucket_date(row["bucket_start"]),
                    "transaction_count": row["transaction_count"] or 0,
                    "revenue": Decimal(str(row["revenue"] or 0)),
                }
                for row in rows
            ]
        finally:
            conn.close()

    @staticmethod
    def get_category_sales(start_date, end_date, limit=6):
        conn = TransactionDB._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            range_start, range_end = TransactionDB._date_window_bounds(start_date, end_date)
            tx_id = TransactionDB._tx_id("t")
            tx_date = TransactionDB._tx_date("t")
            completed_filter = TransactionDB._completed_sales_filter("t")
            item_amount = TransactionDB._item_amount("ti")
            product_pk = TransactionDB._product_pk("p")
            cursor.execute(
                f"""
                SELECT
                    COALESCE(NULLIF(p.category, ''), 'Uncategorized') AS category,
                    COALESCE(SUM(ti.quantity), 0) AS quantity_sold,
                    COALESCE(SUM({item_amount}), 0) AS sales_total
                FROM transaction_items ti
                JOIN transactions t ON ti.transaction_id = {tx_id}
                LEFT JOIN products p ON ti.product_id = {product_pk}
                WHERE t.is_voided = 0
                  AND {tx_date} >= %s
                  AND {tx_date} < %s
                  AND {completed_filter}
                GROUP BY category
                ORDER BY sales_total DESC, quantity_sold DESC, category ASC
                LIMIT %s
                """,
                (range_start, range_end, limit),
            )
            rows = cursor.fetchall()
            return [
                {
                    "category": row["category"],
                    "quantity_sold": row["quantity_sold"] or 0,
                    "sales_total": Decimal(str(row["sales_total"] or 0)),
                }
                for row in rows
            ]
        finally:
            conn.close()

    @staticmethod
    def get_best_sellers(limit=20, start_date=None, end_date=None, category=None, sort_by="quantity"):
        category = TransactionDB._normalize_category(category)
        sort_field = "sales_total" if str(sort_by).strip().lower() == "revenue" else "quantity_sold"
        secondary_field = "quantity_sold" if sort_field == "sales_total" else "sales_total"

        conn = TransactionDB._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            tx_id = TransactionDB._tx_id("t")
            tx_date = TransactionDB._tx_date("t")
            item_amount = TransactionDB._item_amount("ti")
            product_pk = TransactionDB._product_pk("p")
            product_name_expr = "COALESCE(ti.product_name, p.name, 'Unknown Product')"
            completed_filter = TransactionDB._completed_sales_filter("t")
            query = f"""
                SELECT
                    COALESCE(ti.product_id, {product_pk}) AS product_id,
                    {product_name_expr} AS product_name,
                    COALESCE(NULLIF(p.category, ''), 'Uncategorized') AS category,
                    COALESCE(SUM(ti.quantity), 0) AS quantity_sold,
                    COALESCE(SUM({item_amount}), 0) AS sales_total
                FROM transaction_items ti
                JOIN transactions t ON ti.transaction_id = {tx_id}
                LEFT JOIN products p ON ti.product_id = {product_pk}
                WHERE t.is_voided = 0
                  AND {completed_filter}
            """
            params = []
            if start_date and end_date:
                range_start, range_end = TransactionDB._date_window_bounds(start_date, end_date)
                query += f" AND {tx_date} >= %s AND {tx_date} < %s"
                params.extend([range_start, range_end])
            if category is not None:
                query += " AND COALESCE(NULLIF(p.category, ''), 'Uncategorized') = %s"
                params.append(category)

            query += f"""
                GROUP BY product_id, product_name, category
                ORDER BY {sort_field} DESC, {secondary_field} DESC, product_name ASC
            """
            if limit is not None:
                query += " LIMIT %s"
                params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [
                {
                    "product_id": row["product_id"],
                    "product_name": row["product_name"],
                    "category": row["category"],
                    "quantity_sold": row["quantity_sold"] or 0,
                    "sales_total": Decimal(str(row["sales_total"] or 0)),
                }
                for row in rows
            ]
        finally:
            conn.close()

    @staticmethod
    def void_transaction(transaction_id):
        conn = TransactionDB._get_connection()
        cursor = conn.cursor()
        try:
            tx_id = TransactionDB._tx_id()
            cursor.execute(
                f"""
                UPDATE transactions
                SET is_voided = 1,
                    online_order_status = CASE
                        WHEN order_source = 'Online Orders' THEN 'voided'
                        ELSE online_order_status
                    END
                WHERE {tx_id} = %s
                """,
                (transaction_id,),
            )
            conn.commit()
        finally:
            conn.close()
