"""Suggested selling price calculation.

    cost_local          = cost_usd * exchange_rate
    selling_price_local = cost_local * (1 + margin_percentage / 100)

Money is handled with ``Decimal`` end to end and rounded half-up to 2 decimals
only at the edges, which is what an accountant expects (floats would drift).
"""
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.conf import settings
from django.utils import timezone

from books.models import Book
from books.services.exchange_rate import ExchangeRate, get_exchange_rate

TWO_PLACES = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


@dataclass
class PriceCalculation:
    book_id: int
    cost_usd: Decimal
    exchange_rate: Decimal
    cost_local: Decimal
    margin_percentage: Decimal
    selling_price_local: Decimal
    currency: str
    calculation_timestamp: datetime
    rate_source: str
    rate_provider: str
    fallback_used: bool

    def as_dict(self):
        return asdict(self)


def calculate_price(
    book: Book,
    currency: Optional[str] = None,
    margin_percentage: Optional[Decimal] = None,
    persist: bool = True,
    use_cache: bool = True,
) -> PriceCalculation:
    """Convert ``book.cost_usd`` to the local currency and apply the margin.

    When ``persist`` is true the resulting price is stored on the book, which
    is what ``POST /books/{id}/calculate-price`` does.
    """
    currency = (currency or settings.DEFAULT_LOCAL_CURRENCY).strip().upper()
    if margin_percentage is None:
        margin_percentage = Decimal(str(settings.DEFAULT_MARGIN_PERCENTAGE))
    margin_percentage = Decimal(str(margin_percentage))

    quote: ExchangeRate = get_exchange_rate(currency, use_cache=use_cache)

    cost_usd = Decimal(book.cost_usd)
    cost_local_exact = cost_usd * quote.rate
    selling_exact = cost_local_exact * (Decimal("1") + margin_percentage / Decimal("100"))

    cost_local = money(cost_local_exact)
    selling_price_local = money(selling_exact)
    calculated_at = timezone.now()

    if persist:
        book.selling_price_local = selling_price_local
        book.selling_price_currency = quote.currency
        book.price_calculated_at = calculated_at
        book.save(
            update_fields=[
                "selling_price_local",
                "selling_price_currency",
                "price_calculated_at",
                "updated_at",
            ]
        )

    return PriceCalculation(
        book_id=book.id,
        cost_usd=money(cost_usd),
        exchange_rate=quote.rate,
        cost_local=cost_local,
        margin_percentage=margin_percentage,
        selling_price_local=selling_price_local,
        currency=quote.currency,
        calculation_timestamp=calculated_at,
        rate_source=quote.source,
        rate_provider=quote.provider,
        fallback_used=quote.is_fallback,
    )
