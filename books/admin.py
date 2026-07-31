from django.contrib import admin

from books.models import Book


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "author",
        "isbn",
        "cost_usd",
        "selling_price_local",
        "selling_price_currency",
        "stock_quantity",
        "category",
        "supplier_country",
    )
    list_filter = ("category", "supplier_country")
    search_fields = ("title", "author", "isbn", "isbn_normalized")
    readonly_fields = ("isbn_normalized", "created_at", "updated_at", "price_calculated_at")
    ordering = ("-created_at",)
