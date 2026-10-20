"""Tests for user registration and authentication.

All tests run against DemoBackend (in-memory) so no real DB is required.
The MySQL service layer is covered by tests/test_services_mysql.py which
requires a live database.
"""
import pytest

from utils.demo_backend import DemoBackend, ServiceError


@pytest.fixture
def be():
    return DemoBackend(seed=False)


# ---------------------------------------------------------------- registration
class TestRegisterUser:
    def test_register_business_success(self, be):
        u = be.register_user("Alice", "alice@test.com", "pass1234", "business", "Alice Co", "Delhi")
        assert u["email"] == "alice@test.com"
        assert u["role"] == "business"
        assert u["org_name"] == "Alice Co"

    def test_register_ngo_success(self, be):
        u = be.register_user("Bob", "bob@test.com", "pass1234", "ngo", "Bob NGO", "Mumbai")
        assert u["role"] == "ngo"

    def test_duplicate_email_raises(self, be):
        be.register_user("Alice", "dup@test.com", "pass1234", "business", "Co", "Delhi")
        with pytest.raises(ServiceError, match="already exists"):
            be.register_user("Bob", "dup@test.com", "pass1234", "business", "Co2", "Delhi")

    def test_missing_name_raises(self, be):
        with pytest.raises(ServiceError, match="name is required"):
            be.register_user("", "x@x.com", "pass1234", "business", "Co", "Delhi")

    def test_missing_org_raises(self, be):
        with pytest.raises(ServiceError, match="Organisation name"):
            be.register_user("Alice", "x@x.com", "pass1234", "business", "", "Delhi")

    def test_short_password_raises(self, be):
        with pytest.raises(ServiceError, match="8 characters"):
            be.register_user("Alice", "x@x.com", "short", "business", "Co", "Delhi")

    def test_invalid_email_raises(self, be):
        with pytest.raises(ServiceError, match="valid email"):
            be.register_user("Alice", "not-an-email", "pass1234", "business", "Co", "Delhi")

    def test_invalid_role_raises(self, be):
        with pytest.raises(ServiceError, match="account type"):
            be.register_user("Alice", "x@x.com", "pass1234", "admin", "Co", "Delhi")

    def test_password_not_stored_in_public_dict(self, be):
        u = be.register_user("Alice", "x@x.com", "pass1234", "business", "Co", "Delhi")
        for key in u:
            assert "password" not in key.lower() and "hash" not in key.lower()


# ---------------------------------------------------------------- authentication
class TestAuthenticate:
    def test_correct_credentials_return_user(self, be):
        be.register_user("Alice", "alice@test.com", "pass1234", "business", "Co", "Delhi")
        u = be.authenticate("alice@test.com", "pass1234")
        assert u is not None
        assert u["email"] == "alice@test.com"

    def test_wrong_password_returns_none(self, be):
        be.register_user("Alice", "alice@test.com", "pass1234", "business", "Co", "Delhi")
        assert be.authenticate("alice@test.com", "wrongpass") is None

    def test_unknown_email_returns_none(self, be):
        assert be.authenticate("nobody@test.com", "pass1234") is None

    def test_email_case_insensitive(self, be):
        be.register_user("Alice", "Alice@Test.COM", "pass1234", "business", "Co", "Delhi")
        assert be.authenticate("alice@test.com", "pass1234") is not None

    def test_empty_credentials_return_none(self, be):
        assert be.authenticate("", "") is None


# ---------------------------------------------------------------- get_user
class TestGetUser:
    def test_get_existing_user(self, be):
        u = be.register_user("Alice", "a@t.com", "pass1234", "business", "Co", "Delhi")
        fetched = be.get_user(u["id"])
        assert fetched["email"] == "a@t.com"

    def test_get_nonexistent_returns_none(self, be):
        assert be.get_user(99999) is None
