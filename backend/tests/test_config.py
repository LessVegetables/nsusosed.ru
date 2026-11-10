"""Settings that depend on each other."""

from app.config import Settings


def test_cookie_is_secure_on_https_and_relaxed_on_plain_http():
    prod = Settings(public_origin="https://nsusosed.ru", email_mode="log")
    assert prod.cookie_secure is True and prod.cookie_name == "__Host-nsusosed"
    # Safari drops Secure cookies on http://localhost, and __Host- requires Secure.
    dev = Settings(public_origin="http://localhost:8080", email_mode="log")
    assert dev.cookie_secure is False and dev.cookie_name == "nsusosed"
