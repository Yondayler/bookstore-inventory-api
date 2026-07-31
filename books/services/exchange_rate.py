"""Client for the public exchange-rate provider.

Responsibilities:

* fetch USD -> * rates from ``https://api.exchangerate-api.com/v4/latest/USD``
* cache the payload for ``EXCHANGE_RATE_CACHE_TTL`` seconds so a burst of price
  calculations does not hammer the provider
* degrade gracefully: when the provider is unreachable or answers with
  garbage, fall back to the rates configured in ``FALLBACK_EXCHANGE_RATES``
  (business rule: "si la API de cambio falla, usar tasa por defecto")
* raise :class:`ExchangeRateUnavailable` (HTTP 503) only when there is no
  fallback either, and :class:`UnsupportedCurrency` (HTTP 400) when the
  currency simply does not exist
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, Optional

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from books.exceptions import ExchangeRateUnavailable, UnsupportedCurrency

logger = logging.getLogger(__name__)

CACHE_KEY = "exchange_rates:USD"

SOURCE_API = "api"
SOURCE_CACHE = "cache"
SOURCE_FALLBACK = "fallback"


@dataclass(frozen=True)
class ExchangeRate:
    """A single USD -> ``currency`` quote plus its provenance."""

    currency: str
    rate: Decimal
    source: str
    fetched_at: datetime
    provider: str = "exchangerate-api.com"

    @property
    def is_fallback(self) -> bool:
        return self.source == SOURCE_FALLBACK


def _to_decimal(value) -> Optional[Decimal]:
    try:
        rate = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return rate if rate > 0 else None


def _fetch_rates_from_provider() -> Dict[str, Decimal]:
    """Call the provider. Raises ``requests.RequestException`` / ``ValueError``."""
    response = requests.get(
        settings.EXCHANGE_RATE_API_URL,
        timeout=settings.EXCHANGE_RATE_TIMEOUT,
        headers={"Accept": "application/json"},
    )
    response.raise_for_status()
    payload = response.json()

    raw_rates = payload.get("rates") if isinstance(payload, dict) else None
    if not isinstance(raw_rates, dict) or not raw_rates:
        raise ValueError("Exchange rate provider returned no 'rates' object.")

    rates = {}
    for currency, value in raw_rates.items():
        rate = _to_decimal(value)
        if rate is not None:
            rates[str(currency).upper()] = rate
    if not rates:
        raise ValueError("Exchange rate provider returned no usable rates.")
    return rates


def get_rates(use_cache: bool = True):
    """Return ``(rates, source)`` — never raises; returns ``({}, ...)`` on failure."""
    if use_cache:
        cached = cache.get(CACHE_KEY)
        if cached:
            return {k: Decimal(str(v)) for k, v in cached.items()}, SOURCE_CACHE

    try:
        rates = _fetch_rates_from_provider()
    except (requests.RequestException, ValueError, TypeError) as exc:
        logger.warning("Exchange rate provider unavailable (%s): %s", type(exc).__name__, exc)
        return {}, SOURCE_FALLBACK

    cache.set(
        CACHE_KEY,
        {k: str(v) for k, v in rates.items()},
        timeout=settings.EXCHANGE_RATE_CACHE_TTL,
    )
    return rates, SOURCE_API


def get_exchange_rate(currency: str, use_cache: bool = True) -> ExchangeRate:
    """Return the USD -> ``currency`` rate, falling back to a default if needed.

    :raises UnsupportedCurrency: HTTP 400 — the provider does not quote it.
    :raises ExchangeRateUnavailable: HTTP 503 — provider down, no default rate.
    """
    currency = (currency or settings.DEFAULT_LOCAL_CURRENCY).strip().upper()
    fallback_rates = settings.FALLBACK_EXCHANGE_RATES

    rates, source = get_rates(use_cache=use_cache)

    if rates:
        rate = rates.get(currency)
        if rate is not None:
            return ExchangeRate(
                currency=currency, rate=rate, source=source, fetched_at=timezone.now()
            )
        # The provider answered but does not know this currency: that is a
        # client error, not an outage.
        raise UnsupportedCurrency(
            {
                "currency": [
                    f"'{currency}' is not a currency quoted by the exchange rate "
                    f"provider."
                ]
            }
        )

    fallback = fallback_rates.get(currency)
    if fallback is None:
        raise ExchangeRateUnavailable(
            f"The exchange rate provider is unavailable and no fallback rate is "
            f"configured for '{currency}'. Please try again later."
        )

    logger.warning("Using fallback exchange rate for %s: %s", currency, fallback)
    return ExchangeRate(
        currency=currency,
        rate=fallback,
        source=SOURCE_FALLBACK,
        fetched_at=timezone.now(),
        provider="configured-fallback",
    )
