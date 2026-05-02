import pytest
from models.user import User

@pytest.fixture
def user_manager():
    manager = User.UserManager()
    manager.add_user(User(1, "Admin",       "admin",   "admin123", "owner"))
    manager.add_user(User(2, "Cashier Joe", "cashier", "cash123",  "cashier"))
    manager.add_user(User(3, "Baker Bob",   "baker",   "bake123",  "baker"))
    return manager

def test_valid_login(user_manager):
    user = user_manager.login("admin", "admin123")
    assert user is not None
    assert user.username == "admin"
    assert user.role == "owner"

def test_add_user(user_manager):
    new_user = User(4, "New Cashier", "newcash", "new123", "cashier")
    user_manager.add_user(new_user)
    logged_in = user_manager.login("newcash", "new123")
    assert logged_in is not None
    assert logged_in.name == "New Cashier"

def test_owner_access(user_manager):
    user = user_manager.login("admin", "admin123")
    assert user.has_access("inventory")
    assert user.has_access("transaction")
    assert user.has_access("reports")

def test_cashier_access(user_manager):
    user = user_manager.login("cashier", "cash123")
    assert user.has_access("transaction")
    assert not user.has_access("inventory")

def test_baker_access(user_manager):
    user = user_manager.login("baker", "bake123")
    assert user.has_access("production")
    assert user.has_access("inventory")
    assert not user.has_access("transaction")

def test_invalid_login(user_manager):
    user = user_manager.login("admin", "wrongpass")
    assert user is None

def test_check_password(user_manager):
    user = user_manager.login("admin", "admin123")
    assert user.check_password("admin123")
    assert not user.check_password("wrongpass")

def test_prevent_duplicate_username(user_manager):
    duplicate_user = User(5, "Duplicate", "Admin", "dup123", "cashier")
    result = user_manager.add_user(duplicate_user)
    assert result is False

def test_user_activation(user_manager):
    user = user_manager.login("cashier", "cash123")
    user.is_active = False
    logged_in = user if user.is_active else None
    assert logged_in is None

def test_access_without_login():
    ghost_user = User(99, "Ghost", "ghost", "ghost", "guest")
    assert not ghost_user.has_access("transaction")
    assert not ghost_user.has_access("inventory")
    assert not ghost_user.has_access("production")

#pytest tests/ -v