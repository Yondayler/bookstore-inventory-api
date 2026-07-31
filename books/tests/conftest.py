from decimal import Decimal

import pytest
import responses
from django.conf import settings
from django.core.cache import cache
from rest_framework.test import APIClient

from books.models import Book

EXCHANGE_API_URL = "https://api.exchangerate-api.com/v4/latest/USD"

SAMPLE_RATES_PAYLOAD = {
    "base": "USD",
    "date": "2025-01-15",
    "rates": {"USD": 1, "EUR": 0.85, "MXN": 18.5, "COP": 4050.0, "GBP": 0.78},
}


@pytest.fixture(autouse=True)
def isolated_cache(settings):
    """Give every test a private, in-memory cache.

    Two reasons: rates must not leak between tests, and the production cache
    backend is the database, which would force even the pure validator tests to
    request database access. The database backend itself is covered by
    ``test_pricing.test_database_cache_backend_round_trip``.
    """
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "tests",
        }
    }
    # Production forces HTTPS; the test client speaks plain HTTP, so the
    # redirect would turn every assertion into a 301.
    settings.SECURE_SSL_REDIRECT = False
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def book_payload():
    return {
        "title": "El Quijote",
        "author": "Miguel de Cervantes",
        "isbn": "978-84-376-0494-7",
        "cost_usd": "15.99",
        "stock_quantity": 25,
        "category": "Literatura Clásica",
        "supplier_country": "ES",
    }


@pytest.fixture
def book(db):
    return Book.objects.create(
        title="El Quijote",
        author="Miguel de Cervantes",
        isbn="978-84-376-0494-7",
        cost_usd=Decimal("15.99"),
        stock_quantity=25,
        category="Literatura Clásica",
        supplier_country="ES",
    )


@pytest.fixture
def mock_exchange_api():
    """Successful response from the exchange rate provider."""
    with responses.RequestsMock() as mock:
        mock.add(responses.GET, EXCHANGE_API_URL, json=SAMPLE_RATES_PAYLOAD, status=200)
        yield mock


@pytest.fixture
def mock_exchange_api_down():
    """Provider returning 500 — the fallback rate must kick in."""
    with responses.RequestsMock() as mock:
        mock.add(responses.GET, EXCHANGE_API_URL, json={"error": "boom"}, status=500)
        yield mock
