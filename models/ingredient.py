class Ingredient:
    def __init__(self, ingredient_id, name, unit, quantity, reorder_level):
        self.ingredient_id = ingredient_id
        self.name = name
        self.unit = unit
        self.quantity = quantity
        self.reorder_level = reorder_level

    def is_low_stock(self):
        return self.quantity <= self.reorder_level

    def deduct(self, amount):
        if amount > self.quantity:
            print(f"Not enough {self.name}! Available: {self.quantity} {self.unit}")
            return False
        self.quantity -= amount
        return True

    def display(self):
        status = "LOW STOCK" if self.is_low_stock() else "OK"
        print(f"ID: {self.ingredient_id}")
        print(f"Name: {self.name}")
        print(f"Quantity: {self.quantity} {self.unit}")
        print(f"Reorder Level: {self.reorder_level} {self.unit}")
        print(f"Status: {status}")

    def __str__(self):
        return f"{self.name}: {self.quantity} {self.unit}"