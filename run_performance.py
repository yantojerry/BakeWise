import time
import statistics
from datetime import date, timedelta
from contextlib import contextmanager

from mysql.connector import Error
from database.db import get_connection as project_get_connection


# =========================================================
# TEST SETTINGS
# The runner will prefer these values, then automatically
# fall back to real records that already exist in the DB.
# =========================================================
TEST_SETTINGS = {
    "runs": 5,

    # Existing login account in your system
    "test_username": "admin",

    # Preferred product IDs. The script will fall back automatically
    # if these do not exist in the current database.
    "preferred_product_ids": [3, 5],

    # Temporary values for write/update simulation
    "temp_stock_add": 1,
    "search_keyword": "a",
}


# =========================================================
# DATABASE CONNECTION
# =========================================================
@contextmanager
def get_connection():
    conn = None
    try:
        conn = project_get_connection()
        conn.autocommit = False
        yield conn
    finally:
        if conn and conn.is_connected():
            conn.close()


# =========================================================
# HELPER
# =========================================================
def timed_call(func, conn, runtime_settings):
    start = time.perf_counter()
    func(conn, runtime_settings)
    end = time.perf_counter()
    return end - start


# =========================================================
# RUNTIME TARGETS
# =========================================================
def resolve_runtime_settings(conn):
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT
                p.id,
                p.name,
                p.category,
                p.price,
                p.shelf_life_days,
                COALESCE(
                    SUM(
                        CASE
                            WHEN ib.expiry_date >= CURDATE() AND ib.quantity > 0
                            THEN ib.quantity
                            ELSE 0
                        END
                    ),
                    0
                ) AS active_qty,
                COALESCE(
                    SUM(
                        CASE
                            WHEN ib.quantity > 0
                            THEN ib.quantity
                            ELSE 0
                        END
                    ),
                    0
                ) AS total_qty
            FROM products p
            LEFT JOIN inventory_batches ib ON ib.product_id = p.id
            GROUP BY p.id, p.name, p.category, p.price, p.shelf_life_days
            ORDER BY p.id ASC
            """
        )
        products = cursor.fetchall()
        if not products:
            raise RuntimeError("No products found in the database.")

        cursor.execute("SELECT username FROM users ORDER BY id ASC")
        users = cursor.fetchall()
        if not users:
            raise RuntimeError("No users found in the database.")

        products_by_id = {row["id"]: row for row in products}
        resolved_products = []
        for product_id in TEST_SETTINGS.get("preferred_product_ids", []):
            row = products_by_id.get(product_id)
            if row and row not in resolved_products:
                resolved_products.append(row)
        for row in products:
            if row not in resolved_products:
                resolved_products.append(row)

        primary_product = resolved_products[0]
        secondary_product = resolved_products[1] if len(resolved_products) > 1 else resolved_products[0]

        stock_product = next(
            (row for row in resolved_products if float(row["active_qty"] or 0) > 0),
            next(
                (row for row in resolved_products if float(row["total_qty"] or 0) > 0),
                resolved_products[0],
            ),
        )

        cursor.execute(
            """
            SELECT id, product_id, quantity
            FROM inventory_batches
            WHERE product_id = %s
            ORDER BY
                CASE WHEN expiry_date >= CURDATE() AND quantity > 0 THEN 0 ELSE 1 END,
                quantity DESC,
                production_date ASC,
                id ASC
            LIMIT 1
            """,
            (stock_product["id"],),
        )
        writable_batch = cursor.fetchone()
        if not writable_batch:
            cursor.execute(
                """
                SELECT id, product_id, quantity
                FROM inventory_batches
                ORDER BY
                    CASE WHEN expiry_date >= CURDATE() AND quantity > 0 THEN 0 ELSE 1 END,
                    quantity DESC,
                    production_date ASC,
                    id ASC
                LIMIT 1
                """
            )
            writable_batch = cursor.fetchone()
        if not writable_batch:
            raise RuntimeError("No inventory batch was found for stock simulation.")

        configured_username = str(TEST_SETTINGS.get("test_username") or "").strip()
        available_usernames = {row["username"] for row in users}
        login_username = configured_username if configured_username in available_usernames else users[0]["username"]

        search_keyword = str(TEST_SETTINGS.get("search_keyword") or "").strip()
        if not search_keyword:
            search_keyword = primary_product["name"][:1]

        return {
            "login_username": login_username,
            "product_id_1": primary_product["id"],
            "product_id_2": secondary_product["id"],
            "stock_batch_id": writable_batch["id"],
            "production_product_id": secondary_product["id"],
            "production_shelf_life_days": int(secondary_product["shelf_life_days"] or 0),
            "search_keyword": search_keyword,
        }
    finally:
        cursor.close()


# =========================================================
# TEST FUNCTIONS
# =========================================================

def test_login(conn, runtime_settings):
    """
    Simulates the current login flow, which looks up a user by username.
    """
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT id, username, role
        FROM users
        WHERE username = %s
        LIMIT 1
    """
    cursor.execute(query, (runtime_settings["login_username"],))
    cursor.fetchone()
    cursor.close()


def test_fetch_products(conn, runtime_settings):
    """
    Simulates loading product list.
    """
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT id, name, category, price, shelf_life_days
        FROM products
        ORDER BY id ASC
    """
    cursor.execute(query)
    cursor.fetchall()
    cursor.close()


def test_inventory_view(conn, runtime_settings):
    """
    Simulates viewing inventory page.
    """
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT
            ib.id AS batch_id,
            p.id AS product_id,
            p.name,
            ib.quantity,
            ib.production_date,
            ib.expiry_date
        FROM inventory_batches ib
        JOIN products p ON p.id = ib.product_id
        WHERE ib.expiry_date >= CURDATE()
          AND ib.quantity > 0
        ORDER BY ib.production_date ASC, ib.id ASC
    """
    cursor.execute(query)
    cursor.fetchall()
    cursor.close()


def test_dashboard_counts(conn, runtime_settings):
    """
    Simulates dashboard summary queries.
    """
    cursor = conn.cursor(dictionary=True)

    queries = [
        "SELECT COUNT(*) AS total_products FROM products",
        """
        SELECT COUNT(*) AS active_batches
        FROM inventory_batches
        WHERE expiry_date >= CURDATE()
          AND quantity > 0
        """,
        """
        SELECT COALESCE(SUM(quantity), 0) AS total_active_stock
        FROM inventory_batches
        WHERE expiry_date >= CURDATE()
          AND quantity > 0
        """,
    ]

    for query in queries:
        cursor.execute(query)
        cursor.fetchone()

    cursor.close()


def test_single_product_lookup(conn, runtime_settings):
    """
    Simulates retrieving one product, like in details/edit/produce flow.
    """
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT id, name, category, price, shelf_life_days
        FROM products
        WHERE id = %s
        LIMIT 1
    """
    cursor.execute(query, (runtime_settings["product_id_1"],))
    cursor.fetchone()
    cursor.close()


def test_update_stock_simulation(conn, runtime_settings):
    """
    Simulates stock update by editing one existing inventory batch.
    Data stays unchanged because the whole run is rolled back.
    """
    cursor = conn.cursor()

    # Read current quantity
    cursor.execute(
        "SELECT quantity FROM inventory_batches WHERE id = %s LIMIT 1",
        (runtime_settings["stock_batch_id"],),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValueError(f"Inventory batch ID {runtime_settings['stock_batch_id']} not found.")

    current_qty = row[0]
    new_qty = current_qty + TEST_SETTINGS["temp_stock_add"]

    # Update quantity
    cursor.execute(
        "UPDATE inventory_batches SET quantity = %s WHERE id = %s",
        (new_qty, runtime_settings["stock_batch_id"]),
    )

    # Optional verification
    cursor.execute(
        "SELECT quantity FROM inventory_batches WHERE id = %s LIMIT 1",
        (runtime_settings["stock_batch_id"],),
    )
    cursor.fetchone()

    cursor.close()


def test_production_simulation(conn, runtime_settings):
    """
    Simulates production by creating a temporary inventory batch.
    Data stays unchanged because of rollback.
    """
    cursor = conn.cursor()

    production_date = date.today()
    expiry_date = production_date + timedelta(days=max(runtime_settings["production_shelf_life_days"], 1))
    cursor.execute(
        """
        INSERT INTO inventory_batches (product_id, quantity, production_date, expiry_date)
        VALUES (%s, %s, %s, %s)
        """,
        (
            runtime_settings["production_product_id"],
            max(TEST_SETTINGS["temp_stock_add"], 1),
            production_date,
            expiry_date,
        ),
    )

    cursor.execute(
        """
        SELECT quantity
        FROM inventory_batches
        WHERE product_id = %s
        ORDER BY id DESC
        LIMIT 1
        """,
        (runtime_settings["production_product_id"],),
    )
    cursor.fetchone()

    cursor.close()


def test_search_products(conn, runtime_settings):
    """
    Simulates search/filter function.
    """
    cursor = conn.cursor(dictionary=True)
    query = """
        SELECT id, name, category, price, shelf_life_days
        FROM products
        WHERE name LIKE %s
        ORDER BY name ASC
    """
    cursor.execute(query, (f"%{runtime_settings['search_keyword']}%",))
    cursor.fetchall()
    cursor.close()


# =========================================================
# MAIN BENCHMARK RUNNER
# =========================================================
def run_one_benchmark(run_number):
    results = {}

    with get_connection() as conn:
        try:
            runtime_settings = resolve_runtime_settings(conn)

            # Every run begins fresh and ends with rollback
            results["Login Module"] = timed_call(test_login, conn, runtime_settings)
            results["Fetch Products"] = timed_call(test_fetch_products, conn, runtime_settings)
            results["Inventory View"] = timed_call(test_inventory_view, conn, runtime_settings)
            results["Dashboard Counts"] = timed_call(test_dashboard_counts, conn, runtime_settings)
            results["Single Product Lookup"] = timed_call(test_single_product_lookup, conn, runtime_settings)
            results["Search Products"] = timed_call(test_search_products, conn, runtime_settings)
            results["Update Stock Simulation"] = timed_call(test_update_stock_simulation, conn, runtime_settings)
            results["Production Simulation"] = timed_call(test_production_simulation, conn, runtime_settings)

            # Rollback so no data is permanently changed
            conn.rollback()

        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"Run {run_number} failed: {e}")

    return results


def print_run_results(run_number, results):
    print(f"\n========== RUN {run_number} ==========")
    total = 0.0
    for module_name, elapsed in results.items():
        print(f"{module_name:<28} : {elapsed:.6f} seconds")
        total += elapsed
    print(f"{'TOTAL RUN TIME':<28} : {total:.6f} seconds")


def print_average_results(all_runs):
    print(f"\n========== AVERAGE RESULTS ({len(all_runs)} RUNS) ==========")

    module_names = list(all_runs[0].keys())
    grand_totals = []

    for module_name in module_names:
        values = [run[module_name] for run in all_runs]
        avg = statistics.mean(values)
        print(f"{module_name:<28} : {avg:.6f} seconds")

    for run in all_runs:
        grand_totals.append(sum(run.values()))

    print(f"{'AVERAGE TOTAL RUN TIME':<28} : {statistics.mean(grand_totals):.6f} seconds")


def print_summary_table(all_runs):
    print("\n========== SUMMARY TABLE ==========")

    module_names = list(all_runs[0].keys())
    run_count = len(all_runs)

    run_headers = "".join(f" {f'Run {index}':>10}" for index in range(1, run_count + 1))
    header = f"{'Module':<28}{run_headers} {'Average':>12}"
    print(header)
    print("-" * len(header))

    for module_name in module_names:
        values = [run[module_name] for run in all_runs]
        avg = statistics.mean(values)
        values_text = "".join(f" {value:>10.6f}" for value in values)
        print(f"{module_name:<28}{values_text} {avg:>12.6f}")

    total_values = [sum(run.values()) for run in all_runs]
    total_avg = statistics.mean(total_values)

    print("-" * len(header))
    totals_text = "".join(f" {value:>10.6f}" for value in total_values)
    print(f"{'TOTAL':<28}{totals_text} {total_avg:>12.6f}")


def main():
    all_runs = []

    print("Starting BakeWise performance benchmark...")
    print(f"Total runs: {TEST_SETTINGS['runs']}")
    print("Note: All write operations are rolled back, so your data will stay unchanged.")

    for i in range(1, TEST_SETTINGS["runs"] + 1):
        results = run_one_benchmark(i)
        all_runs.append(results)
        print_run_results(i, results)

    print_summary_table(all_runs)
    print_average_results(all_runs)

    print("\nBenchmark completed successfully.")


if __name__ == "__main__":
    try:
        main()
    except Error as db_err:
        print(f"Database error: {db_err}")
    except Exception as e:
        print(f"Error: {e}")
