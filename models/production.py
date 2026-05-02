from datetime import date

class Production:
    def __init__(self, production_id, product, quantity, recipe, production_date=None):
        self.production_id = production_id
        self.product = product
        self.quantity = quantity
        self.recipe = recipe
        self.production_date = production_date or date.today()
        self.expiry_date = self._compute_expiry()
        self.is_cancelled = False

    def _compute_expiry(self):
        from datetime import timedelta
        return self.production_date + timedelta(days=self.product.shelf_life_days)

    def produce(self):
        if self.is_cancelled:
            print("This batch was already cancelled.")
            return False

        if not self.recipe.can_produce(self.quantity):
            print(f"Cannot produce {self.quantity} {self.product.name}. Not enough ingredients.")
            return False

        # Deduct ingredients
        for item in self.recipe.ingredients:
            needed = item["amount"] * self.quantity
            item["ingredient"].deduct(needed)

        print(f"Successfully produced {self.quantity} {self.product.name}")
        print(f"Production Date: {self.production_date}")
        print(f"Expiry Date:     {self.expiry_date}")
        return True

    def cancel(self):
        self.is_cancelled = True
        print(f"Batch {self.production_id} cancelled.")

    def display(self):
        status = "Cancelled" if self.is_cancelled else "Active"
        print(f"Batch ID: {self.production_id}")
        print(f"Product: {self.product.name}")
        print(f"Quantity: {self.quantity}")
        print(f"Production Date: {self.production_date}")
        print(f"Expiry Date: {self.expiry_date}")
        print(f"Status: {status}")