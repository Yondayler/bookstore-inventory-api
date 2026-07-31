from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from books.validators import normalize_isbn


class Book(models.Model):
    """A title in the chain's inventory.

    Business rules enforced here (and mirrored by the serializer so clients get
    a 400 instead of a 500):

    * ``cost_usd`` must be greater than 0
    * ``stock_quantity`` cannot be negative
    * ``isbn`` must be unique — hyphenated and plain forms of the same ISBN
      collide thanks to ``isbn_normalized``
    """

    title = models.CharField(max_length=255, db_index=True)
    author = models.CharField(max_length=255, db_index=True)
    isbn = models.CharField(max_length=20, unique=True)
    # Digits-only copy of `isbn`, kept in sync on save; uniqueness is enforced
    # on this column so "978-84-376-0494-7" == "9788437604947".
    isbn_normalized = models.CharField(max_length=13, unique=True, editable=False)
    cost_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Purchase cost in US dollars. Must be greater than 0.",
    )
    selling_price_local = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Filled in by POST /books/{id}/calculate-price.",
    )
    selling_price_currency = models.CharField(max_length=3, blank=True, default="")
    price_calculated_at = models.DateTimeField(null=True, blank=True)
    stock_quantity = models.PositiveIntegerField(
        default=0, validators=[MinValueValidator(0)]
    )
    category = models.CharField(max_length=100, blank=True, default="", db_index=True)
    supplier_country = models.CharField(
        max_length=2, blank=True, default="", help_text="ISO 3166-1 alpha-2 code, e.g. ES."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "book"
        verbose_name_plural = "books"
        constraints = [
            models.CheckConstraint(
                check=models.Q(cost_usd__gt=Decimal("0")), name="book_cost_usd_positive"
            ),
            models.CheckConstraint(
                check=models.Q(stock_quantity__gte=0), name="book_stock_not_negative"
            ),
        ]
        indexes = [models.Index(fields=["category", "stock_quantity"])]

    def __str__(self):
        return f"{self.title} ({self.isbn})"

    def save(self, *args, **kwargs):
        self.isbn_normalized = normalize_isbn(self.isbn)
        if self.supplier_country:
            self.supplier_country = self.supplier_country.upper()
        if self.selling_price_currency:
            self.selling_price_currency = self.selling_price_currency.upper()
        super().save(*args, **kwargs)

    @property
    def is_low_stock(self):
        return self.stock_quantity <= 10
