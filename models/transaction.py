from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP


class Transaction:
    def __init__(self, transaction_id, cashier_name):
        self.transaction_id = transaction_id
        self.cashier_name = cashier_name
        self.date = date.today()
        self.items = []
        self.payment_method = None
        self.amount_paid = Decimal("0.00")
        self.recorded_total = None
        self.is_voided = False
        self.service_mode = "Take Out"
        self.order_source = "Walk-In"
        self.customer_number = None
        self.pickup_date_from = None
        self.pickup_date_to = None
        self.online_order_status = None
        self.accepted_at = None
        self.processed_at = None

    def _product_id(self, product):
        return getattr(product, "product_id", getattr(product, "id", None))

    def _available_quantity(self, product, inventory_or_subtotal):
        if inventory_or_subtotal is None:
            return None

        if isinstance(inventory_or_subtotal, (int, float, Decimal)):
            return None

        product_id = self._product_id(product)
        if product_id is None:
            return None

        getter = getattr(inventory_or_subtotal, "get_available_quantity", None)
        if callable(getter):
            try:
                return getter(product_id)
            except TypeError:
                return None

        batches = getattr(inventory_or_subtotal, "batches", None)
        if batches is None:
            return None

        total = 0
        for batch in batches:
            batch_product = getattr(batch, "product", None)
            batch_product_id = getattr(batch_product, "product_id", getattr(batch, "product_id", None))
            if batch_product_id != product_id:
                continue

            is_expired = getattr(batch, "is_expired", None)
            if callable(is_expired) and is_expired():
                continue

            total += getattr(batch, "quantity", 0)
        return total

    def add_item(self, product, quantity, inventory_or_subtotal=None):
        quantity = int(quantity)
        if quantity <= 0:
            print(f"Could not add {product.name} - invalid quantity")
            return False

        available_quantity = self._available_quantity(product, inventory_or_subtotal)
        if available_quantity is not None and quantity > available_quantity:
            print(f"Could not add {product.name} - insufficient stock")
            return False

        subtotal = Decimal(str(product.price)) * Decimal(quantity)
        self.items.append(
            {
                "product": product,
                "quantity": quantity,
                "subtotal": subtotal,
            }
        )
        print(f"Added {quantity}x {product.name} to cart")
        return True

    def _to_decimal(self, value):
        if value is None or value == "":
            return Decimal("0.00")
        try:
            if isinstance(value, Decimal):
                return value
            text = str(value).strip().upper().replace(",", "").replace("PHP", "").replace("₱", "")
            return Decimal(text or "0")
        except Exception:
            return Decimal("0.00")

    def _money(self, value):
        return f"{self._to_decimal(value):.2f}"

    def get_total(self):
        if self.items:
            total = sum(self._to_decimal(item.get("subtotal")) for item in self.items)
        elif self.recorded_total is not None:
            total = self._to_decimal(self.recorded_total)
        else:
            total = Decimal("0.00")
        return Decimal(total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def checkout(self, payment_method, amount_paid, inventory=None):
        if not self.items:
            print("Cart is empty!")
            return False

        total = self.get_total()
        amount_paid = self._to_decimal(amount_paid).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        if amount_paid < total:
            print(f"Insufficient payment! Total is PHP {self._money(total)}")
            return False

        self.payment_method = payment_method
        self.amount_paid = amount_paid
        print(f"\nTransaction #{self.transaction_id} successful!")
        return True

    def get_change(self):
        change = self._to_decimal(self.amount_paid) - self.get_total()
        if change < 0:
            change = Decimal("0.00")
        return change.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def void(self):
        self.is_voided = True
        if self.order_source == "Online Orders":
            self.online_order_status = "voided"
            if self.processed_at is None:
                self.processed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"Transaction #{self.transaction_id} has been voided.")
        return True

    def void_transaction(self):
        return self.void()

    def mark_online_processed(self, processed_at=None):
        if self.order_source != "Online Orders":
            return
        self.online_order_status = "processed"
        self.processed_at = processed_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def mark_online_accepted(self, accepted_at=None):
        if self.order_source != "Online Orders":
            return
        self.online_order_status = "accepted"
        self.accepted_at = accepted_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def print_receipt(self):
        print("=" * 35)
        print("         BAKEWISE RECEIPT")
        print("=" * 35)
        print(f"Receipt No.:   {self.customer_number or '-'}")
        print(f"Transaction ID: {self.transaction_id}")
        print(f"Date:          {self.date}")
        print(f"Cashier:       {self.cashier_name}")
        print(f"Service Mode:  {self.service_mode}")
        print(f"Order Source:  {self.order_source}")
        if self.pickup_date_from or self.pickup_date_to:
            print(f"Pickup From:   {self.pickup_date_from or '-'}")
            print(f"Pickup Until:  {self.pickup_date_to or self.pickup_date_from or '-'}")
        print("-" * 35)
        for item in self.items:
            print(
                f"{item['product'].name} x{item['quantity']}"
                f"  PHP {self._money(item.get('subtotal'))}"
            )
        print("-" * 35)
        print(f"TOTAL:         PHP {self._money(self.get_total())}")
        print(f"Payment:       {self.payment_method}")
        print(f"Amount Paid:   PHP {self._money(self.amount_paid)}")
        print(f"Change:        PHP {self._money(self.get_change())}")
        print("=" * 35)
        if self.is_voided:
            print("*** VOIDED ***")
