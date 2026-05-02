class Recipe:
    def __init__(self, product_id):
        self.product_id = product_id
        self.ingredients = []  # list of {ingredient, amount_needed}

    def add_ingredient(self, ingredient, amount_needed):
        self.ingredients.append({
            "ingredient": ingredient,
            "amount": amount_needed
        })
        print(f"Added {ingredient.name} x{amount_needed} to recipe")

    def display(self):
        print(f"Recipe for Product ID: {self.product_id}")
        for item in self.ingredients:
            print(f"  - {item['ingredient'].name}: {item['amount']} {item['ingredient'].unit}")

    def can_produce(self, quantity):
        for item in self.ingredients:
            needed = item["amount"] * quantity
            if item["ingredient"].quantity < needed:
                print(f"Not enough {item['ingredient'].name}! "
                      f"Need {needed} {item['ingredient'].unit}, "
                      f"have {item['ingredient'].quantity} {item['ingredient'].unit}")
                return False
        return True