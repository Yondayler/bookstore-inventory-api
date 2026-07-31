from django.db.models import Q
from django.http import Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from books.models import Book
from books.serializers import (
    BookSerializer,
    PriceCalculationRequestSerializer,
    PriceCalculationResponseSerializer,
)
from books.services.pricing import calculate_price

ORDERING_FIELDS = {
    "title",
    "author",
    "cost_usd",
    "stock_quantity",
    "category",
    "created_at",
    "updated_at",
    "selling_price_local",
}


def _positive_int(value, field_name):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValidationError({field_name: [f"{field_name} must be an integer."]})
    if parsed < 0:
        raise ValidationError({field_name: [f"{field_name} cannot be negative."]})
    return parsed


@extend_schema_view(
    list=extend_schema(
        summary="List books",
        description=(
            "Returns the paginated inventory. Supports filtering by `category`, "
            "`author`, `supplier_country`, free-text `q` (title/author/ISBN), "
            "`min_stock`/`max_stock` and `ordering`."
        ),
        parameters=[
            OpenApiParameter("category", OpenApiTypes.STR, description="Filter by category."),
            OpenApiParameter("author", OpenApiTypes.STR, description="Filter by author."),
            OpenApiParameter("q", OpenApiTypes.STR, description="Search title, author or ISBN."),
            OpenApiParameter("supplier_country", OpenApiTypes.STR, description="ISO alpha-2 code."),
            OpenApiParameter("min_stock", OpenApiTypes.INT),
            OpenApiParameter("max_stock", OpenApiTypes.INT),
            OpenApiParameter(
                "ordering",
                OpenApiTypes.STR,
                description=f"One of: {', '.join(sorted(ORDERING_FIELDS))} (prefix with '-' to reverse).",
            ),
        ],
    ),
    retrieve=extend_schema(summary="Get a book by id"),
    create=extend_schema(summary="Create a book"),
    update=extend_schema(summary="Replace a book"),
    partial_update=extend_schema(summary="Partially update a book"),
    destroy=extend_schema(summary="Delete a book"),
)
class BookViewSet(viewsets.ModelViewSet):
    """CRUD for the book inventory plus the price calculation endpoint."""

    queryset = Book.objects.all()
    serializer_class = BookSerializer
    lookup_value_regex = r"[0-9]+"

    def get_object(self):
        """Same as DRF's, but with a 404 message that names the book."""
        try:
            return super().get_object()
        except (Http404, NotFound):
            raise NotFound(
                f"Book with id {self.kwargs.get(self.lookup_field)} was not found."
            )

    def get_queryset(self):
        queryset = Book.objects.all()
        params = self.request.query_params

        category = params.get("category")
        if category:
            queryset = queryset.filter(category__icontains=category.strip())

        author = params.get("author")
        if author:
            queryset = queryset.filter(author__icontains=author.strip())

        supplier_country = params.get("supplier_country")
        if supplier_country:
            queryset = queryset.filter(supplier_country__iexact=supplier_country.strip())

        search = params.get("q") or params.get("search")
        if search:
            search = search.strip()
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(author__icontains=search)
                | Q(isbn__icontains=search)
                | Q(isbn_normalized__icontains=search.replace("-", ""))
            )

        if "min_stock" in params:
            queryset = queryset.filter(
                stock_quantity__gte=_positive_int(params["min_stock"], "min_stock")
            )
        if "max_stock" in params:
            queryset = queryset.filter(
                stock_quantity__lte=_positive_int(params["max_stock"], "max_stock")
            )

        ordering = params.get("ordering")
        if ordering:
            field = ordering.lstrip("-")
            if field not in ORDERING_FIELDS:
                raise ValidationError(
                    {
                        "ordering": [
                            f"Cannot order by '{field}'. Allowed: "
                            f"{', '.join(sorted(ORDERING_FIELDS))}."
                        ]
                    }
                )
            queryset = queryset.order_by(ordering)

        return queryset

    @extend_schema(
        summary="Search books by category",
        description="`GET /books/search?category=Literatura` — case-insensitive partial match.",
        parameters=[
            OpenApiParameter(
                "category",
                OpenApiTypes.STR,
                required=True,
                description="Category to search for.",
            )
        ],
    )
    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        category = request.query_params.get("category")
        if not category or not category.strip():
            raise ValidationError(
                {"category": ["The 'category' query parameter is required."]}
            )
        queryset = Book.objects.filter(category__icontains=category.strip())
        return self._paginated(queryset)

    @extend_schema(
        summary="List books running low on stock",
        description="`GET /books/low-stock?threshold=10` — books with stock at or below the threshold.",
        parameters=[
            OpenApiParameter(
                "threshold",
                OpenApiTypes.INT,
                description="Stock threshold (inclusive). Defaults to 10.",
            )
        ],
    )
    @action(detail=False, methods=["get"], url_path="low-stock")
    def low_stock(self, request):
        threshold = _positive_int(request.query_params.get("threshold", 10), "threshold")
        queryset = Book.objects.filter(stock_quantity__lte=threshold).order_by(
            "stock_quantity", "title"
        )
        return self._paginated(queryset, extra={"threshold": threshold})

    @extend_schema(
        summary="Calculate the suggested selling price",
        description=(
            "Converts `cost_usd` to the local currency using a live USD exchange "
            "rate, applies the profit margin (40% by default), stores the result "
            "in `selling_price_local` and returns the detailed calculation.\n\n"
            "If the exchange rate provider is unreachable a configured fallback "
            "rate is used and `fallback_used` is `true`. A 503 is returned only "
            "when no fallback exists for the requested currency."
        ),
        request=PriceCalculationRequestSerializer,
        responses={200: PriceCalculationResponseSerializer},
    )
    @action(detail=True, methods=["post"], url_path="calculate-price")
    def calculate_price(self, request, pk=None):
        book = self.get_object()

        request_serializer = PriceCalculationRequestSerializer(data=request.data or {})
        request_serializer.is_valid(raise_exception=True)
        options = request_serializer.validated_data

        calculation = calculate_price(
            book,
            currency=options.get("currency"),
            margin_percentage=options.get("margin_percentage"),
        )
        return Response(calculation.as_dict(), status=status.HTTP_200_OK)

    # -- helpers ------------------------------------------------------------
    def _paginated(self, queryset, extra=None):
        page = self.paginate_queryset(queryset)
        if page is not None:
            response = self.get_paginated_response(self.get_serializer(page, many=True).data)
            if extra:
                response.data.update(extra)
            return response
        data = {"count": queryset.count(), "results": self.get_serializer(queryset, many=True).data}
        if extra:
            data.update(extra)
        return Response(data)
