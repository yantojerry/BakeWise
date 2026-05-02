class Product:
    def __init__(
        self,
        product_id=None,
        name=None,
        category="Unknown",
        price=0,
        shelf_life_days=0,
        **kwargs,
    ):
        legacy_id = kwargs.pop("id", None)
        if kwargs:
            unexpected = ", ".join(sorted(kwargs))
            raise TypeError(f"Unexpected Product arguments: {unexpected}")

        if product_id is None:
            product_id = legacy_id

        self.product_id = product_id
        self.id = product_id
        self.name = name
        self.category = category
        self.price = price
        self.shelf_life_days = shelf_life_days

    def display(self):
        print(f"ID: {self.product_id}")
        print(f"Name: {self.name}")
        print(f"Category: {self.category}")
        print(f"Price: ₱{self.price:.2f}")
        print(f"Shelf Life: {self.shelf_life_days} days")

    def __str__(self):
        return f"{self.name} - ₱{self.price:.2f}"
