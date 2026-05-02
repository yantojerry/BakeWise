from datetime import date, timedelta

from database.db import get_connection
from models.production import Production
from models.product import Product


class ProductionDB:
    @staticmethod
    def _build_production(row):
        product = Product(
            row["product_id"],
            row["name"],
            row["category"],
            row["price"],
            row["shelf_life_days"],
        )
        production = Production(
            row["id"],
            product,
            row["quantity"],
            recipe=None,
            production_date=row["production_date"],
        )
        production.expiry_date = row["expiry_date"]
        production.is_cancelled = False
        return production

    @staticmethod
    def log_production(product_id, product, quantity, production_date=None):
        """Logs a production batch and returns the new production id."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            prod_date = production_date or date.today()
            expiry_date = prod_date + timedelta(days=product.shelf_life_days)

            query = """
                INSERT INTO production_batches
                (product_id, quantity, production_date, expiry_date)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(query, (product_id, quantity, prod_date, expiry_date))
            conn.commit()
            return cursor.lastrowid
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_productions(product_name=None, production_date=None, category=None, limit=None):
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            query = """
                SELECT pb.*, p.name, p.category, p.price, p.shelf_life_days
                FROM production_batches pb
                JOIN products p ON pb.product_id = p.id
                WHERE 1 = 1
            """
            params = []

            if product_name:
                query += " AND LOWER(p.name) LIKE %s"
                params.append(f"%{str(product_name).strip().lower()}%")

            if production_date:
                query += " AND DATE(pb.production_date) = %s"
                params.append(production_date)

            if category and str(category).strip() != "All Categories":
                query += " AND p.category = %s"
                params.append(category)

            query += " ORDER BY pb.production_date DESC, pb.id DESC"

            if limit is not None:
                query += " LIMIT %s"
                params.append(int(limit))

            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [ProductionDB._build_production(row) for row in rows]
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_all_productions():
        return ProductionDB.get_productions()

    @staticmethod
    def get_active_productions():
        return ProductionDB.get_productions()

    @staticmethod
    def cancel_production(production_id):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM production_batches WHERE id = %s", (production_id,))
            conn.commit()
        finally:
            cursor.close()
            conn.close()
