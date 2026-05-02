from datetime import date, timedelta

from database.db import get_connection
from models.ingredient import Ingredient


class IngredientDB:
    @staticmethod
    def get_ingredient_count():
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM ingredients")
            row = cursor.fetchone()
            return int(row[0] or 0) if row else 0
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def get_low_stock_count():
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM ingredients WHERE quantity <= reorder_level")
            row = cursor.fetchone()
            return int(row[0] or 0) if row else 0
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def get_all_ingredients():
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM ingredients")
            rows = cursor.fetchall()
            return [Ingredient(r['id'], r['name'], r['unit'],
                               r['quantity'], r['reorder_level']) for r in rows]
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def get_ingredient(ingredient_id):
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM ingredients WHERE id = %s", (ingredient_id,))
            r = cursor.fetchone()
            if r:
                return Ingredient(r['id'], r['name'], r['unit'],
                                  r['quantity'], r['reorder_level'])
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def add_ingredient(name, unit, quantity, reorder_level):
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            query = "INSERT INTO ingredients (name, unit, quantity, reorder_level) VALUES (%s, %s, %s, %s)"
            cursor.execute(query, (name, unit, quantity, reorder_level))
            conn.commit()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def update_ingredient(ingredient_id, quantity, reorder_level):
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            query = "UPDATE ingredients SET quantity = %s, reorder_level = %s WHERE id = %s"
            cursor.execute(query, (quantity, reorder_level, ingredient_id))
            conn.commit()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def delete_ingredient(ingredient_id):
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES LIKE 'recipe_items'")
            if cursor.fetchone():
                cursor.execute("DELETE FROM recipe_items WHERE ingredient_id = %s", (ingredient_id,))
            cursor.execute("DELETE FROM ingredients WHERE id = %s", (ingredient_id,))
            deleted_count = cursor.rowcount
            conn.commit()
            return deleted_count
        except Exception:
            if conn:
                conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def deduct_ingredient(ingredient_id, amount):
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM ingredients WHERE id = %s", (ingredient_id,))
            r = cursor.fetchone()
            if not r:
                print("Ingredient not found.")
                return False
            if amount > r['quantity']:
                print(f"Not enough {r['name']}! Available: {r['quantity']} {r['unit']}")
                return False
            new_qty = r['quantity'] - amount
            cursor.execute("UPDATE ingredients SET quantity = %s WHERE id = %s",
                           (new_qty, ingredient_id))
            conn.commit()
            return True
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def get_low_stock():
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM ingredients WHERE quantity <= reorder_level")
            rows = cursor.fetchall()
            return [Ingredient(r['id'], r['name'], r['unit'],
                               r['quantity'], r['reorder_level']) for r in rows]
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def _bucket_start(value, group_by):
        if group_by == "weekly":
            return value - timedelta(days=value.weekday())
        if group_by == "monthly":
            return value.replace(day=1)
        return value

    @staticmethod
    def _increment_bucket(current, group_by):
        if group_by == "weekly":
            return current + timedelta(days=7)
        if group_by == "monthly":
            year = current.year + (1 if current.month == 12 else 0)
            month = 1 if current.month == 12 else current.month + 1
            return current.replace(year=year, month=month, day=1)
        return current + timedelta(days=1)

    @staticmethod
    def _bucket_label(current, group_by):
        if group_by == "weekly":
            return current.strftime("%b %d")
        if group_by == "monthly":
            return current.strftime("%b %Y")
        return current.strftime("%b %d")

    @staticmethod
    def _low_stock_timeline(start_date, end_date, group_by, low_count):
        normalized_group = str(group_by or "daily").strip().lower()
        if normalized_group not in {"daily", "weekly", "monthly"}:
            normalized_group = "daily"

        cursor = IngredientDB._bucket_start(start_date, normalized_group)
        final_bucket = IngredientDB._bucket_start(end_date, normalized_group)
        points = []
        while cursor <= final_bucket:
            points.append(
                {
                    "label": IngredientDB._bucket_label(cursor, normalized_group),
                    "value": float(low_count),
                }
            )
            cursor = IngredientDB._increment_bucket(cursor, normalized_group)
        return points

    @staticmethod
    def get_low_stock_history_report(start_date, end_date, group_by="daily"):
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM ingredients ORDER BY name ASC")
            raw_rows = cursor.fetchall()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        rows = []
        healthy_count = 0
        critical_count = 0
        low_count = 0

        for raw in raw_rows:
            quantity = float(raw.get("quantity") or 0)
            reorder_level = float(raw.get("reorder_level") or 0)
            ingredient = Ingredient(
                raw.get("id"),
                raw.get("name") or "Unnamed Ingredient",
                raw.get("unit") or "",
                quantity,
                reorder_level,
            )

            if quantity <= 0:
                status = "Critical"
                critical_count += 1
            elif quantity <= reorder_level:
                status = "Low"
                low_count += 1
            else:
                healthy_count += 1
                continue

            shortage = max(reorder_level - quantity, 0.0)
            coverage_ratio = 0.0 if reorder_level <= 0 else max(min(quantity / reorder_level, 1.0), 0.0)
            rows.append(
                {
                    "ingredient": ingredient,
                    "quantity": quantity,
                    "reorder_level": reorder_level,
                    "shortage": shortage,
                    "coverage_ratio": coverage_ratio,
                    "status": status,
                }
            )

        rows.sort(
            key=lambda item: (
                0 if item["status"] == "Critical" else 1,
                item["coverage_ratio"],
                -item["shortage"],
                item["ingredient"].name.lower(),
            )
        )

        total_low_count = critical_count + low_count
        today = date.today()
        return {
            "range_start": start_date,
            "range_end": end_date,
            "available_from": None,
            "history_available": False,
            "snapshot_date": today,
            "rows": rows,
            "critical_count": critical_count,
            "low_count": low_count,
            "healthy_count": healthy_count,
            "timeline_points": IngredientDB._low_stock_timeline(start_date, end_date, group_by, total_low_count),
        }
