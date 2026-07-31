import re
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from books.models import Book
from books.validators import validate_isbn

COUNTRY_CODE = re.compile(r"^[A-Za-z]{2}$")


class BookSerializer(serializers.ModelSerializer):
    """Read/write representation of a book.

    ``selling_price_local`` is read-only on purpose: it is produced by
    ``POST /books/{id}/calculate-price`` so it can never disagree with the
    exchange rate it was derived from.
    """

    # Declared explicitly to replace DRF's automatic UniqueValidator with a
    # check that also catches the same ISBN written with different hyphenation.
    isbn = serializers.CharField(max_length=20, validators=[])
    cost_usd = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        error_messages={"min_value": "cost_usd must be greater than 0."},
    )
    stock_quantity = serializers.IntegerField(
        required=False,
        default=0,
        min_value=0,
        error_messages={"min_value": "stock_quantity cannot be negative."},
    )

    class Meta:
        model = Book
        fields = [
            "id",
            "title",
            "author",
            "isbn",
            "cost_usd",
            "selling_price_local",
            "stock_quantity",
            "category",
            "supplier_country",
            "created_at",
            "updated_at",
            "selling_price_currency",
            "price_calculated_at",
        ]
        read_only_fields = [
            "id",
            "selling_price_local",
            "selling_price_currency",
            "price_calculated_at",
            "created_at",
            "updated_at",
        ]

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("title cannot be empty.")
        return value

    def validate_author(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("author cannot be empty.")
        return value

    def validate_isbn(self, value):
        try:
            normalized = validate_isbn(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))

        duplicates = Book.objects.filter(isbn_normalized=normalized)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        existing = duplicates.first()
        if existing is not None:
            raise serializers.ValidationError(
                f"A book with ISBN {existing.isbn} already exists (id={existing.id})."
            )
        return value.strip()

    def validate_supplier_country(self, value):
        value = (value or "").strip()
        if value and not COUNTRY_CODE.match(value):
            raise serializers.ValidationError(
                "supplier_country must be a 2-letter ISO 3166-1 alpha-2 code (e.g. 'ES')."
            )
        return value.upper()

    def validate_category(self, value):
        return (value or "").strip()


class PriceCalculationRequestSerializer(serializers.Serializer):
    """Optional body of ``POST /books/{id}/calculate-price``."""

    currency = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="ISO 4217 code of the local currency. Defaults to DEFAULT_LOCAL_CURRENCY (EUR).",
    )
    margin_percentage = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=6,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("1000"),
        help_text="Profit margin in percent. Defaults to 40.",
    )

    def validate_currency(self, value):
        if value in (None, ""):
            return None
        value = value.strip().upper()
        if not re.match(r"^[A-Z]{3}$", value):
            raise serializers.ValidationError(
                "currency must be a 3-letter ISO 4217 code (e.g. 'EUR')."
            )
        return value


class PriceCalculationResponseSerializer(serializers.Serializer):
    """Documented shape of the price calculation response."""

    book_id = serializers.IntegerField()
    cost_usd = serializers.DecimalField(max_digits=10, decimal_places=2)
    exchange_rate = serializers.DecimalField(max_digits=20, decimal_places=6)
    cost_local = serializers.DecimalField(max_digits=14, decimal_places=2)
    margin_percentage = serializers.DecimalField(max_digits=6, decimal_places=2)
    selling_price_local = serializers.DecimalField(max_digits=14, decimal_places=2)
    currency = serializers.CharField()
    calculation_timestamp = serializers.DateTimeField()
    rate_source = serializers.ChoiceField(choices=["api", "cache", "fallback"])
    rate_provider = serializers.CharField()
    fallback_used = serializers.BooleanField()
