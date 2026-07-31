"""Tests for POST /books/{id}/calculate-price and the exchange rate client."""
from decimal import Decimal

import pytest
import responses

from books.exceptions import ExchangeRateUnavailable
from books.services.exchange_rate import (
    SOURCE_API,
    SOURCE_CACHE,
    SOURCE_FALLBACK,
    get_exchange_rate,
)

from .conftest import EXCHANGE_API_URL, SAMPLE_RATES_PAYLOAD

pytestmark = pytest.mark.django_db


# --- happy path -------------------------------------------------------------


def test_calculate_price_matches_the_specification(api_client, book, mock_exchange_api):
    """15.99 USD * 0.85 = 13.59 EUR, +40% margin = 19.03 EUR."""
    response = api_client.post(f"/books/{book.id}/calculate-price", {}, format="json")

    assert response.status_code == 200, response.data
    body = response.json()
    assert body["book_id"] == book.id
    assert body["cost_usd"] == 15.99
    assert body["exchange_rate"] == 0.85
    assert body["cost_local"] == 13.59
    assert body["margin_percentage"] == 40
    assert body["selling_price_local"] == 19.03
    assert body["currency"] == "EUR"
    assert body["calculation_timestamp"]
    assert body["fallback_used"] is False
    assert body["rate_source"] == SOURCE_API


def test_calculate_price_persists_the_result(api_client, book, mock_exchange_api):
    api_client.post(f"/books/{book.id}/calculate-price", {}, format="json")

    book.refresh_from_db()
    assert book.selling_price_local == Decimal("19.03")
    assert book.selling_price_currency == "EUR"
    assert book.price_calculated_at is not None

    detail = api_client.get(f"/books/{book.id}")
    assert detail.json()["selling_price_local"] == 19.03
    assert detail.json()["selling_price_currency"] == "EUR"


def test_calculate_price_accepts_currency_and_margin_overrides(
    api_client, book, mock_exchange_api
):
    response = api_client.post(
        f"/books/{book.id}/calculate-price",
        {"currency": "mxn", "margin_percentage": "25"},
        format="json",
    )

    assert response.status_code == 200
    body = response.json()
    assert body["currency"] == "MXN"
    assert body["exchange_rate"] == 18.5
    assert body["cost_local"] == 295.82  # 15.99 * 18.5 = 295.815 -> half-up
    assert body["margin_percentage"] == 25
    assert body["selling_price_local"] == 369.77


def test_rates_are_cached_between_calls(api_client, book, mock_exchange_api):
    api_client.post(f"/books/{book.id}/calculate-price", {}, format="json")
    second = api_client.post(f"/books/{book.id}/calculate-price", {}, format="json")

    assert second.json()["rate_source"] == SOURCE_CACHE
    assert len(mock_exchange_api.calls) == 1  # the provider was hit only once


# --- failure handling -------------------------------------------------------


def test_provider_failure_falls_back_to_default_rate(
    api_client, book, mock_exchange_api_down, settings
):
    settings.FALLBACK_EXCHANGE_RATES = {"EUR": Decimal("0.92")}

    response = api_client.post(f"/books/{book.id}/calculate-price", {}, format="json")

    assert response.status_code == 200
    body = response.json()
    assert body["fallback_used"] is True
    assert body["rate_source"] == SOURCE_FALLBACK
    assert body["exchange_rate"] == 0.92
    assert body["cost_local"] == 14.71  # 15.99 * 0.92 = 14.7108
    assert body["selling_price_local"] == 20.60  # 14.7108 * 1.4 = 20.59512


@responses.activate
def test_provider_timeout_falls_back(api_client, book, settings):
    settings.FALLBACK_EXCHANGE_RATES = {"EUR": Decimal("0.92")}
    responses.add(
        responses.GET, EXCHANGE_API_URL, body=responses.ConnectionError("network down")
    )

    response = api_client.post(f"/books/{book.id}/calculate-price", {}, format="json")

    assert response.status_code == 200
    assert response.json()["fallback_used"] is True


def test_503_when_provider_is_down_and_no_fallback_exists(
    api_client, book, mock_exchange_api_down, settings
):
    settings.FALLBACK_EXCHANGE_RATES = {}

    response = api_client.post(f"/books/{book.id}/calculate-price", {}, format="json")

    assert response.status_code == 503
    assert response.data["error"]["code"] == "exchange_rate_unavailable"


def test_400_for_a_currency_the_provider_does_not_quote(
    api_client, book, mock_exchange_api
):
    response = api_client.post(
        f"/books/{book.id}/calculate-price", {"currency": "XYZ"}, format="json"
    )

    assert response.status_code == 400
    assert "currency" in response.data["error"]["details"]


def test_400_for_a_malformed_currency_code(api_client, book):
    response = api_client.post(
        f"/books/{book.id}/calculate-price", {"currency": "euros"}, format="json"
    )

    assert response.status_code == 400
    assert "currency" in response.data["error"]["details"]


def test_400_for_a_negative_margin(api_client, book):
    response = api_client.post(
        f"/books/{book.id}/calculate-price", {"margin_percentage": "-10"}, format="json"
    )

    assert response.status_code == 400
    assert "margin_percentage" in response.data["error"]["details"]


def test_404_when_calculating_the_price_of_an_unknown_book(api_client):
    response = api_client.post("/books/424242/calculate-price", {}, format="json")

    assert response.status_code == 404
    assert response.data["error"]["code"] == "not_found"


# --- exchange rate client ---------------------------------------------------


@responses.activate
def test_get_exchange_rate_reads_the_provider_payload():
    responses.add(responses.GET, EXCHANGE_API_URL, json=SAMPLE_RATES_PAYLOAD, status=200)

    quote = get_exchange_rate("EUR")

    assert quote.rate == Decimal("0.85")
    assert quote.source == SOURCE_API
    assert quote.is_fallback is False


@responses.activate
def test_get_exchange_rate_handles_a_malformed_payload(settings):
    settings.FALLBACK_EXCHANGE_RATES = {"EUR": Decimal("0.92")}
    responses.add(responses.GET, EXCHANGE_API_URL, json={"unexpected": True}, status=200)

    quote = get_exchange_rate("EUR")

    assert quote.is_fallback is True
    assert quote.rate == Decimal("0.92")


@responses.activate
def test_get_exchange_rate_raises_503_without_a_fallback(settings):
    settings.FALLBACK_EXCHANGE_RATES = {}
    responses.add(responses.GET, EXCHANGE_API_URL, body="not json", status=200)

    with pytest.raises(ExchangeRateUnavailable):
        get_exchange_rate("EUR")
