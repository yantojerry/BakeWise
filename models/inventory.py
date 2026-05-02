from datetime import date
from models.product import Product

class InventoryBatch:
    def __init__(
        self,
        batch_id,
        product=None,
        quantity=0,
        production_date=None,
        expiry_date=None,
        product_id=None,
        product_name=None,
    ):
        if product is None:
            product = Product(
                product_id=product_id,
                name=product_name or f"Product {product_id}",
                price=0,
                shelf_life_days=0,
            )

        self.batch_id = batch_id
        self.product = product
        self.product_id = getattr(product, "product_id", product_id)
        self.product_name = getattr(product, "name", product_name)
        self.quantity = quantity
        self.production_date = production_date
        self.expiry_date = expiry_date

    def get_freshness_percent(self):
        if self.production_date is None or self.expiry_date is None:
            return 100.0
        today = date.today()
        total_days = (self.expiry_date - self.production_date).days
        remaining_days = (self.expiry_date - today).days
        if total_days == 0:
            return 0
        percent = (remaining_days / total_days) * 100
        return max(0, min(100, percent))

    def get_freshness_label(self):
        if self.production_date is None or self.expiry_date is None:
            return "FRESH"
        percent = self.get_freshness_percent()
        if percent >= 75:
            return "FRESH"
        elif percent >= 50:
            return "GOOD"
        elif percent >= 25:
            return "AGING"
        elif percent > 0:
            return "STALE"
        else:
            return "EXPIRED"

    def is_expired(self):
        if self.expiry_date is None:
            return False
        return date.today() > self.expiry_date

    def deduct_stock(self, amount):
        if amount > self.quantity:
            print(f"Not enough stock in batch {self.batch_id}")
            return False
        self.quantity -= amount
        return True

    def display(self):
        freshness = self.get_freshness_percent()
        label = self.get_freshness_label()
        print(f"Batch ID:        {self.batch_id}")
        print(f"Product:         {self.product.name}")
        print(f"Quantity:        {self.quantity}")
        print(f"Production Date: {self.production_date}")
        print(f"Expiry Date:     {self.expiry_date}")
        print(f"Freshness:       {freshness:.1f}% — {label}")


class Inventory:
    def __init__(self):
        self.batches = []

    def add_batch(self, batch):
        self.batches.append(batch)
        print(f"Batch {batch.batch_id} added to inventory.")

    def get_active_batches(self):
        return [b for b in self.batches if not b.is_expired() and b.quantity > 0]

    def get_expired_batches(self):
        return [b for b in self.batches if b.is_expired()]

    def get_expiring_soon(self, days=1):
        today = date.today()
        return [b for b in self.batches
                if b.expiry_date is not None and 0 < (b.expiry_date - today).days <= days and b.quantity > 0]

    def get_available_quantity(self, product_id):
        total = 0
        for batch in self.get_active_batches():
            batch_product_id = getattr(batch.product, "product_id", None)
            if batch_product_id == product_id:
                total += batch.quantity
        return total

    def deduct_fifo(self, product_id, amount):
        # Deduct from oldest batch first
        active = [b for b in self.get_active_batches()
                  if b.product.product_id == product_id]
        active.sort(key=lambda b: b.production_date or date.min)

        for batch in active:
            if amount <= 0:
                break
            deducted = min(batch.quantity, amount)
            batch.deduct_stock(deducted)
            amount -= deducted

        if amount > 0:
            print("Not enough stock to complete the sale!")
            return False
        return True

    def display_all(self):
        print("=== STOCK INVENTORY ===")
        active = self.get_active_batches()
        if not active:
            print("No active stock.")
            return
        for batch in active:
            batch.display()
            print("---")
