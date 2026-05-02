from database.db import get_connection
from models.product import Product


class ProductDB:
    @staticmethod
    def get_product_count():
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM products")
            row = cursor.fetchone()
            return int(row[0] or 0) if row else 0
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def get_all_products():
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT id, name, category, price, shelf_life_days
                FROM products
                ORDER BY id DESC
            """)
            rows = cursor.fetchall()

            products = []
            for r in rows:
                products.append(
                    Product(
                        r["id"],
                        r["name"],
                        r["category"],
                        float(r["price"]),
                        int(r["shelf_life_days"])
                    )
                )
            return products
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def get_product(product_id):
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT id, name, category, price, shelf_life_days
                FROM products
                WHERE id = %s
            """, (product_id,))
            r = cursor.fetchone()

            if not r:
                return None

            return Product(
                r["id"],
                r["name"],
                r["category"],
                float(r["price"]),
                int(r["shelf_life_days"])
            )
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def add_product(name, category, price, shelf_life_days):
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            query = """
                INSERT INTO products (name, category, price, shelf_life_days)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(query, (name, category, float(price), int(shelf_life_days)))
            conn.commit()
            return cursor.lastrowid
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def update_product(product_id, name, category, price, shelf_life_days):
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            query = """
                UPDATE products
                SET name = %s, category = %s, price = %s, shelf_life_days = %s
                WHERE id = %s
            """
            cursor.execute(query, (name, category, float(price), int(shelf_life_days), product_id))
            conn.commit()
            return cursor.rowcount
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def delete_product(product_id):
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
            conn.commit()
            return cursor.rowcount
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
