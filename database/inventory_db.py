from datetime import date, timedelta
from database.db import get_connection
from models.inventory import InventoryBatch
from models.product import Product


class InventoryDB:
    _schema_checked = False

    @staticmethod
    def _get_connection():
        conn = get_connection()
        InventoryDB._ensure_schema(conn)
        return conn

    @staticmethod
    def _ensure_schema(conn):
        if InventoryDB._schema_checked:
            return

        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT EXTRA
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'inventory_batches'
                  AND COLUMN_NAME = 'id'
                """
            )
            cursor.fetchone()
        except Exception:
            pass

        InventoryDB._schema_checked = True

    @staticmethod
    def debug_count_batches():
        conn = InventoryDB._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM inventory_batches")
            count = cursor.fetchone()[0]

            cursor.execute("SELECT * FROM inventory_batches LIMIT 10")
            cursor.fetchall()

            return count
        finally:
            conn.close()

    @staticmethod
    def debug_join_batches():
        conn = InventoryDB._get_connection()
        cursor = conn.cursor()
        try:
            query = """
                SELECT
                    ib.id AS batch_id,
                    ib.product_id,
                    ib.quantity,
                    ib.production_date,
                    ib.expiry_date,
                    p.id AS joined_product_id,
                    p.name,
                    p.category,
                    p.price,
                    p.shelf_life_days
                FROM inventory_batches ib
                JOIN products p ON ib.product_id = p.id
                LIMIT 10
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            return rows
        finally:
            conn.close()

    @staticmethod
    def get_active_batch_count():
        conn = InventoryDB._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM inventory_batches
                WHERE DATE(expiry_date) >= %s AND quantity > 0
                """,
                (date.today(),),
            )
            return cursor.fetchone()[0]
        finally:
            conn.close()

    @staticmethod
    def get_expiring_batch_count(days=1):
        conn = InventoryDB._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM inventory_batches
                WHERE DATE(expiry_date) >= %s
                  AND DATE(expiry_date) <= %s
                  AND quantity > 0
                """,
                (date.today(), date.today() + timedelta(days=days)),
            )
            return cursor.fetchone()[0]
        finally:
            conn.close()

    @staticmethod
    def get_inventory_summary(expiring_days=2):
        conn = InventoryDB._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            today = date.today()
            expiring_limit = today + timedelta(days=max(int(expiring_days), 0))
            cursor.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN ib.expiry_date >= %s AND ib.quantity > 0 THEN 1 ELSE 0 END), 0) AS active_batches,
                    COALESCE(SUM(CASE WHEN ib.expiry_date >= %s AND ib.quantity > 0 THEN ib.quantity ELSE 0 END), 0) AS active_quantity,
                    COALESCE(SUM(CASE WHEN ib.expiry_date >= %s AND ib.quantity > 0 THEN ib.quantity * COALESCE(p.price, 0) ELSE 0 END), 0) AS active_value,
                    COALESCE(SUM(CASE WHEN ib.expiry_date >= %s AND ib.expiry_date <= %s AND ib.quantity > 0 THEN 1 ELSE 0 END), 0) AS expiring_batches
                FROM inventory_batches ib
                LEFT JOIN products p ON ib.product_id = p.id
                """,
                (today, today, today, today, expiring_limit),
            )
            row = cursor.fetchone() or {}
            return {
                "active_batches": int(row.get("active_batches") or 0),
                "active_quantity": float(row.get("active_quantity") or 0),
                "active_value": float(row.get("active_value") or 0),
                "expiring_batches": int(row.get("expiring_batches") or 0),
            }
        finally:
            conn.close()

    @staticmethod
    def add_batch(product_id, quantity, production_date, expiry_date):
        conn = InventoryDB._get_connection()
        cursor = conn.cursor()
        try:
            query = """
                INSERT INTO inventory_batches
                (product_id, quantity, production_date, expiry_date)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(query, (product_id, quantity, production_date, expiry_date))
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _build_batch(r):
        product = Product(
            r["product_id"],
            r["name"],
            r["category"],
            r["price"],
            r["shelf_life_days"],
        )
        return InventoryBatch(
            r["batch_id"],
            product,
            r["quantity"],
            r["production_date"],
            r["expiry_date"],
        )

    @staticmethod
    def _fetch_batches(where_clause="", params=()):
        conn = InventoryDB._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            query = """
                SELECT
                    ib.id AS batch_id,
                    ib.product_id,
                    ib.quantity,
                    ib.production_date,
                    ib.expiry_date,
                    p.name,
                    p.category,
                    p.price,
                    p.shelf_life_days
                FROM inventory_batches ib
                JOIN products p ON ib.product_id = p.id
            """
            if where_clause:
                query += " " + where_clause

            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [InventoryDB._build_batch(r) for r in rows]
        except Exception:
            raise
        finally:
            conn.close()

    @staticmethod
    def get_all_batches():
        return InventoryDB._fetch_batches(
            "ORDER BY ib.expiry_date ASC, ib.production_date ASC, ib.id ASC"
        )

    @staticmethod
    def get_active_batches():
        return InventoryDB._fetch_batches(
            "WHERE ib.expiry_date >= %s AND ib.quantity > 0 ORDER BY ib.expiry_date ASC, ib.production_date ASC, ib.id ASC",
            (date.today(),),
        )

    @staticmethod
    def get_expired_batches():
        return InventoryDB._fetch_batches(
            "WHERE ib.expiry_date < %s ORDER BY ib.expiry_date ASC, ib.production_date ASC, ib.id ASC",
            (date.today(),),
        )

    @staticmethod
    def get_expiring_soon(days=7):
        return InventoryDB._fetch_batches(
            "WHERE ib.expiry_date >= %s AND ib.expiry_date <= %s AND ib.quantity > 0 ORDER BY ib.expiry_date ASC, ib.production_date ASC, ib.id ASC",
            (date.today(), date.today() + timedelta(days=days)),
        )

    @staticmethod
    def get_expiring_report(days=14):
        window_days = max(int(days), 0)
        batches = InventoryDB.get_expiring_soon(days=window_days)
        today = date.today()

        rows = []
        product_totals = {}
        for batch in batches:
            days_left = max((batch.expiry_date - today).days, 0)
            row = {
                "batch": batch,
                "days_left": days_left,
                "freshness_percent": batch.get_freshness_percent(),
                "freshness_label": batch.get_freshness_label(),
            }
            rows.append(row)
            product_name = batch.product.name
            product_totals[product_name] = product_totals.get(product_name, 0.0) + float(batch.quantity)

        timeline_points = {}
        if window_days <= 14:
            for day_index in range(window_days + 1):
                label = "Today" if day_index == 0 else f"{day_index}d"
                timeline_points[label] = 0.0
            for row in rows:
                label = "Today" if row["days_left"] == 0 else f"{row['days_left']}d"
                timeline_points[label] = timeline_points.get(label, 0.0) + float(row["batch"].quantity)
        else:
            bucket_count = max((window_days + 6) // 7, 1)
            for bucket in range(bucket_count):
                start_day = bucket * 7
                end_day = min(window_days, start_day + 6)
                timeline_points[f"{start_day}-{end_day}d"] = 0.0
            for row in rows:
                bucket = min(row["days_left"] // 7, bucket_count - 1)
                start_day = bucket * 7
                end_day = min(window_days, start_day + 6)
                label = f"{start_day}-{end_day}d"
                timeline_points[label] = timeline_points.get(label, 0.0) + float(row["batch"].quantity)

        product_points = [
            {"label": name, "value": quantity}
            for name, quantity in sorted(product_totals.items(), key=lambda entry: (-entry[1], entry[0]))[:6]
        ]

        return {
            "window_days": window_days,
            "rows": rows,
            "batch_count": len(rows),
            "product_count": len(product_totals),
            "quantity_at_risk": sum(float(row["batch"].quantity) for row in rows),
            "nearest_expiry": rows[0]["days_left"] if rows else None,
            "timeline_points": [{"label": label, "value": value} for label, value in timeline_points.items()],
            "product_points": product_points,
        }

    @staticmethod
    def get_available_quantity(product_id):
        conn = InventoryDB._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT COALESCE(SUM(quantity), 0)
                FROM inventory_batches
                WHERE product_id = %s
                  AND expiry_date >= %s
                  AND quantity > 0
                """,
                (product_id, date.today()),
            )
            quantity = cursor.fetchone()[0]
            return int(quantity or 0)
        finally:
            conn.close()

    @staticmethod
    def get_available_quantities(product_ids=None):
        if product_ids is not None and len(product_ids) == 0:
            return {}

        conn = InventoryDB._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            params = [date.today()]
            query = """
                SELECT product_id, COALESCE(SUM(quantity), 0) AS quantity
                FROM inventory_batches
                WHERE expiry_date >= %s
                  AND quantity > 0
            """

            if product_ids:
                placeholders = ", ".join(["%s"] * len(product_ids))
                query += f" AND product_id IN ({placeholders})"
                params.extend(product_ids)

            query += " GROUP BY product_id"

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            return {int(row["product_id"]): int(row["quantity"] or 0) for row in rows}
        finally:
            conn.close()

    @staticmethod
    def reserve_fifo(product_id, amount):
        conn = InventoryDB._get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                """
                SELECT id AS batch_id, quantity
                FROM inventory_batches
                WHERE product_id = %s
                  AND expiry_date >= %s
                  AND quantity > 0
                ORDER BY production_date ASC, id ASC
                """,
                (product_id, date.today()),
            )
            batches = cursor.fetchall()
            remaining = int(amount)
            reservation = []

            for batch in batches:
                if remaining <= 0:
                    break

                deducted = min(int(batch["quantity"]), remaining)
                if deducted <= 0:
                    continue

                cursor.execute(
                    """
                    UPDATE inventory_batches
                    SET quantity = quantity - %s
                    WHERE id = %s
                    """,
                    (deducted, batch["batch_id"]),
                )
                reservation.append({"batch_id": batch["batch_id"], "quantity": deducted})
                remaining -= deducted

            if remaining > 0:
                conn.rollback()
                return None

            conn.commit()
            return reservation
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def restore_deductions(deductions):
        if not deductions:
            return True

        conn = InventoryDB._get_connection()
        cursor = conn.cursor()
        try:
            for item in deductions:
                cursor.execute(
                    """
                    UPDATE inventory_batches
                    SET quantity = quantity + %s
                    WHERE id = %s
                    """,
                    (int(item["quantity"]), int(item["batch_id"])),
                )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def deduct_fifo(product_id, amount):
        return InventoryDB.reserve_fifo(product_id, amount) is not None

    @staticmethod
    def update_batch_quantity(batch_id, quantity):
        conn = InventoryDB._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE inventory_batches SET quantity = %s WHERE id = %s",
                (quantity, batch_id),
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
