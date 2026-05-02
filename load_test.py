import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

from database.db import get_connection
from database.product_db import ProductDB
from database.transaction_db import TransactionDB
from models.transaction import Transaction

# ---------- CONFIG ----------
USERS = 20   # change to 10 / 30 / 50
RUNS_PER_USER = 5

# ---------- SIMULATION ----------
def simulate_user(user_id):
    results = []
    
    for _ in range(RUNS_PER_USER):
        start = time.time()
        try:
            # 1. Load products
            products = ProductDB.get_all_products()
            if not products:
                raise Exception("No products found")

            # 2. Pick random items
            selected = random.sample(products, min(2, len(products)))

            # 3. Create transaction
            t = Transaction(None, cashier_name=f"User{user_id}")
            t.payment_method = "Cash"

            for p in selected:
                qty = random.randint(1, 3)
                subtotal = p.price * qty
                t.add_item(p, qty, subtotal)

            # 4. Save transaction (THIS IS THE HEAVY PART)
            TransactionDB.save_transaction(t)

            duration = time.time() - start

            results.append({
                "success": True,
                "time": duration
            })

        except Exception as e:
            results.append({
                "success": False,
                "error": str(e),
                "time": time.time() - start
            })

    return results

# ---------- RUN LOAD ----------
def run_test():
    print(f"\nRunning load test with {USERS} users...\n")

    all_results = []

    with ThreadPoolExecutor(max_workers=USERS) as executor:
        futures = [executor.submit(simulate_user, i) for i in range(USERS)]

        for future in as_completed(futures):
            all_results.extend(future.result())

    # ---------- ANALYSIS ----------
    total = len(all_results)
    success = sum(1 for r in all_results if r["success"])
    failed = total - success
    avg_time = sum(r["time"] for r in all_results) / total

    print("===== LOAD TEST RESULT =====")
    print("Total Requests:", total)
    print("Success:", success)
    print("Failed:", failed)
    print("Average Time:", round(avg_time, 4), "sec")
    print("===========================")

# ---------- START ----------
if __name__ == "__main__":
    run_test()