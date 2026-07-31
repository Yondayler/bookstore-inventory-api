from django.db import connection
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response


@extend_schema(exclude=True)
@api_view(["GET"])
def api_root(request):
    """Entry point: lists the available endpoints."""
    return Response(
        {
            "service": "Bookstore Inventory API",
            "version": "1.0.0",
            "documentation": request.build_absolute_uri("/api/docs"),
            "openapi_schema": request.build_absolute_uri("/api/schema"),
            "endpoints": {
                "create_book": "POST /books",
                "list_books": "GET /books?page=1&page_size=20",
                "retrieve_book": "GET /books/{id}",
                "update_book": "PUT /books/{id}",
                "partial_update_book": "PATCH /books/{id}",
                "delete_book": "DELETE /books/{id}",
                "search_by_category": "GET /books/search?category={category}",
                "low_stock": "GET /books/low-stock?threshold=10",
                "calculate_price": "POST /books/{id}/calculate-price",
                "health": "GET /health",
            },
        }
    )


@extend_schema(exclude=True)
@api_view(["GET"])
def health_check(request):
    """Liveness/readiness probe used by Render and docker-compose."""
    database_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:  # pragma: no cover - only hit when the DB is down
        database_ok = False

    payload = {
        "status": "ok" if database_ok else "degraded",
        "database": "ok" if database_ok else "unavailable",
        "timestamp": timezone.now().isoformat(),
    }
    return Response(payload, status=200 if database_ok else 503)
