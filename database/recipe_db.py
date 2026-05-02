from database.db import get_connection
from models.recipe import Recipe
from models.ingredient import Ingredient


class RecipeDB:
    @staticmethod
    def get_product_ids_with_recipes():
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT product_id FROM recipes")
            rows = cursor.fetchall()
            return {int(row[0]) for row in rows if row and row[0] is not None}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def save_recipe(product_id, ingredients):
        """
        ingredients = list of {"ingredient": Ingredient object, "amount": float}
        Replaces existing recipe for that product.
        """
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Delete old recipe for this product if exists
            cursor.execute("SELECT id FROM recipes WHERE product_id = %s", (product_id,))
            existing = cursor.fetchone()
            if existing:
                cursor.execute("DELETE FROM recipes WHERE product_id = %s", (product_id,))

            # Insert new recipe header
            cursor.execute("INSERT INTO recipes (product_id) VALUES (%s)", (product_id,))
            recipe_id = cursor.lastrowid

            # Insert recipe items
            query = "INSERT INTO recipe_items (recipe_id, ingredient_id, quantity) VALUES (%s, %s, %s)"
            for item in ingredients:
                cursor.execute(query, (recipe_id, item['ingredient'].ingredient_id, item['amount']))

            conn.commit()
            return recipe_id
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def get_recipe(product_id):
        """Returns a Recipe object with all ingredients loaded."""
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)

            # Get recipe header
            cursor.execute("SELECT * FROM recipes WHERE product_id = %s", (product_id,))
            recipe_row = cursor.fetchone()
            if not recipe_row:
                return None

            # Get recipe items with ingredient details
            query = """SELECT ri.quantity, i.id, i.name, i.unit, i.quantity as stock, i.reorder_level
                       FROM recipe_items ri
                       JOIN ingredients i ON ri.ingredient_id = i.id
                       WHERE ri.recipe_id = %s"""
            cursor.execute(query, (recipe_row['id'],))
            rows = cursor.fetchall()

            recipe = Recipe(product_id)
            for r in rows:
                ingredient = Ingredient(r['id'], r['name'], r['unit'],
                                        r['stock'], r['reorder_level'])
                recipe.add_ingredient(ingredient, r['quantity'])
            return recipe
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def get_recipe_id(product_id):
        """Returns the recipe id for a given product."""
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM recipes WHERE product_id = %s", (product_id,))
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def has_recipe(product_id):
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM recipes WHERE product_id = %s", (product_id,))
            count = cursor.fetchone()[0]
            return count > 0
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def delete_recipe(product_id):
        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM recipes WHERE product_id = %s", (product_id,))
            conn.commit()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
