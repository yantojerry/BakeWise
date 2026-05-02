class User:
    ROLES = ["owner", "cashier", "baker"]

    def __init__(self, user_id, name, username, password, role):
        self.user_id = user_id
        self.name = name
        self.username = username.lower()
        self.password = password
        self.role = role.lower()
        self.is_active = True

    def check_password(self, password):
        return self.password == password

    def has_access(self, module):
        access_map = {
            "owner":   ["dashboard", "products", "ingredients",
                        "recipe", "production", "inventory",
                        "transaction", "reports", "settings"],
            "cashier": ["transaction"],
            "baker":   ["production", "inventory", "ingredients"]
        }
        return module in access_map.get(self.role, [])

    def display(self):
        print(f"ID:       {self.user_id}")
        print(f"Name:     {self.name}")
        print(f"Username: {self.username}")
        print(f"Role:     {self.role.upper()}")
        print(f"Active:   {self.is_active}")

    def __str__(self):
        return f"{self.name} ({self.role})"

    class UserManager:

        def __init__(self):
            self.users = []

        def login(self, username, password):
            for user in self.users:
                # case-insensitive username comparison
                if user.username == username.lower() and user.check_password(password):
                    if not user.is_active:
                        print("User is deactivated.")
                        return None
                    print(f"Welcome, {user.name}! Logged in as {user.role.upper()}")
                    return user
            print("Invalid username or password.")
            return None

        def add_user(self, user):
            # case-insensitive duplicate check
            if any(u.username == user.username.lower() for u in self.users):
                print(f"Username '{user.username}' already exists.")
                return False
            self.users.append(user)
            return True

        def display_all(self):
            print("=== ALL USERS ===")
            for user in self.users:
                user.display()
                print("---")


# Standalone UserManager (for main.py compatibility)
class UserManager:
    def __init__(self):
        self.users = []

    def add_user(self, user):
        # case-insensitive duplicate check
        if any(u.username == user.username.lower() for u in self.users):
            print(f"Username '{user.username}' already exists.")
            return False
        self.users.append(user)
        return True

    def login(self, username, password):
        for user in self.users:
            # case-insensitive username comparison
            if user.username == username.lower() and user.check_password(password):
                if not user.is_active:
                    print("User is deactivated.")
                    return None
                print(f"Welcome, {user.name}! Logged in as {user.role.upper()}")
                return user
        print("Invalid username or password.")
        return None

    def display_all(self):
        print("=== ALL USERS ===")
        for user in self.users:
            user.display()
            print("---")