"""End-to-end tests for the CRUD endpoints and the business rules."""
from decimal import Decimal

import pytest

from books.models import Book

pytestmark = pytest.mark.django_db


# --- create -----------------------------------------------------------------


def test_create_book(api_client, book_payload):
    response = api_client.post("/books", book_payload, format="json")

    assert response.status_code == 201, response.data
    body = response.json()  # the rendered payload, as a client sees it
    assert body["id"] > 0
    assert body["title"] == "El Quijote"
    assert body["isbn"] == "978-84-376-0494-7"
    assert body["cost_usd"] == 15.99
    assert body["selling_price_local"] is None
    assert body["stock_quantity"] == 25
    assert body["supplier_country"] == "ES"
    assert body["created_at"] and body["updated_at"]
    assert Book.objects.count() == 1


def test_create_book_accepts_trailing_slash(api_client, book_payload):
    response = api_client.post("/books/", book_payload, format="json")
    assert response.status_code == 201


@pytest.mark.parametrize(
    "field,value",
    [
        ("cost_usd", "0"),
        ("cost_usd", "-5.00"),
        ("stock_quantity", -1),
        ("isbn", "123"),
        ("isbn", "not-an-isbn"),
        ("title", ""),
        ("supplier_country", "SPAIN"),
    ],
)
def test_create_book_rejects_invalid_values(api_client, book_payload, field, value):
    book_payload[field] = value
    response = api_client.post("/books", book_payload, format="json")

    assert response.status_code == 400
    assert response.data["error"]["code"] == "validation_error"
    assert field in response.data["error"]["details"]


def test_create_book_requires_mandatory_fields(api_client):
    response = api_client.post("/books", {}, format="json")

    assert response.status_code == 400
    details = response.data["error"]["details"]
    assert {"title", "author", "isbn", "cost_usd"} <= set(details)


def test_duplicate_isbn_is_rejected(api_client, book_payload):
    assert api_client.post("/books", book_payload, format="json").status_code == 201

    response = api_client.post("/books", book_payload, format="json")
    assert response.status_code == 400
    assert "already exists" in response.data["error"]["details"]["isbn"][0]
    assert Book.objects.count() == 1


def test_duplicate_isbn_detected_across_hyphenation(api_client, book_payload):
    api_client.post("/books", book_payload, format="json")

    book_payload["isbn"] = "9788437604947"  # same ISBN, no hyphens
    response = api_client.post("/books", book_payload, format="json")

    assert response.status_code == 400
    assert "already exists" in response.data["error"]["details"]["isbn"][0]


# --- read -------------------------------------------------------------------


def test_list_books_is_paginated(api_client):
    for index in range(25):
        Book.objects.create(
            title=f"Book {index}",
            author="Author",
            isbn=f"978000000{index:04d}",
            cost_usd=Decimal("10.00"),
            stock_quantity=index,
            category="Test",
        )

    response = api_client.get("/books?page_size=10")

    assert response.status_code == 200
    assert response.data["count"] == 25
    assert response.data["total_pages"] == 3
    assert len(response.data["results"]) == 10
    assert response.data["next"] is not None


def test_retrieve_book(api_client, book):
    response = api_client.get(f"/books/{book.id}")

    assert response.status_code == 200
    assert response.data["id"] == book.id
    assert response.data["title"] == "El Quijote"


def test_retrieve_unknown_book_returns_404(api_client):
    response = api_client.get("/books/99999")

    assert response.status_code == 404
    assert response.data["error"]["code"] == "not_found"


def test_unknown_endpoint_returns_json_404(api_client):
    response = api_client.get("/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# --- update / delete --------------------------------------------------------


def test_update_book_with_put(api_client, book, book_payload):
    book_payload["title"] = "Don Quijote de la Mancha"
    book_payload["stock_quantity"] = 12

    response = api_client.put(f"/books/{book.id}", book_payload, format="json")

    assert response.status_code == 200, response.data
    book.refresh_from_db()
    assert book.title == "Don Quijote de la Mancha"
    assert book.stock_quantity == 12


def test_partial_update_book(api_client, book):
    response = api_client.patch(f"/books/{book.id}", {"stock_quantity": 3}, format="json")

    assert response.status_code == 200
    book.refresh_from_db()
    assert book.stock_quantity == 3


def test_update_keeps_its_own_isbn(api_client, book, book_payload):
    """Re-sending the book's own ISBN must not trip the duplicate check."""
    response = api_client.put(f"/books/{book.id}", book_payload, format="json")
    assert response.status_code == 200


def test_delete_book(api_client, book):
    response = api_client.delete(f"/books/{book.id}")

    assert response.status_code == 204
    assert Book.objects.count() == 0


def test_delete_unknown_book_returns_404(api_client):
    assert api_client.delete("/books/12345").status_code == 404


# --- optional endpoints -----------------------------------------------------


@pytest.fixture
def catalogue(db):
    Book.objects.create(
        title="Rayuela",
        author="Julio Cortázar",
        isbn="9788437604947",
        cost_usd=Decimal("18.75"),
        stock_quantity=3,
        category="Literatura Clásica",
    )
    Book.objects.create(
        title="Clean Code",
        author="Robert C. Martin",
        isbn="9780132350884",
        cost_usd=Decimal("42.90"),
        stock_quantity=40,
        category="Tecnología",
    )
    Book.objects.create(
        title="La Sombra del Viento",
        author="Carlos Ruiz Zafón",
        isbn="9780143034902",
        cost_usd=Decimal("14.25"),
        stock_quantity=0,
        category="Misterio",
    )


def test_search_by_category(api_client, catalogue):
    response = api_client.get("/books/search?category=Tecnolog")

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["title"] == "Clean Code"


def test_search_without_category_returns_400(api_client, catalogue):
    response = api_client.get("/books/search")

    assert response.status_code == 400
    assert "category" in response.data["error"]["details"]


def test_low_stock_default_threshold(api_client, catalogue):
    response = api_client.get("/books/low-stock")

    assert response.status_code == 200
    assert response.data["threshold"] == 10
    titles = [item["title"] for item in response.data["results"]]
    assert titles == ["La Sombra del Viento", "Rayuela"]  # ordered by stock asc


def test_low_stock_custom_threshold(api_client, catalogue):
    response = api_client.get("/books/low-stock?threshold=50")

    assert response.status_code == 200
    assert response.data["count"] == 3


def test_low_stock_rejects_invalid_threshold(api_client, catalogue):
    response = api_client.get("/books/low-stock?threshold=abc")

    assert response.status_code == 400
    assert "threshold" in response.data["error"]["details"]


def test_list_filters_and_ordering(api_client, catalogue):
    assert api_client.get("/books?q=cortázar").data["count"] == 1
    assert api_client.get("/books?category=Misterio").data["count"] == 1
    assert api_client.get("/books?min_stock=1").data["count"] == 2

    ordered = api_client.get("/books?ordering=cost_usd").data["results"]
    assert [item["title"] for item in ordered][0] == "La Sombra del Viento"

    invalid = api_client.get("/books?ordering=nope")
    assert invalid.status_code == 400


@pytest.mark.parametrize(
    "path",
    [
        "/books?q=%00nulo",
        "/books?category=%00",
        "/books?author=%00",
        "/books?supplier_country=%00",
        "/books/search?category=%00nulo",
    ],
)
def test_null_bytes_in_query_params_return_400(api_client, catalogue, path):
    """PostgreSQL rejects NUL bytes, so they must be caught before the ORM."""
    response = api_client.get(path)

    assert response.status_code == 400
    assert response.data["error"]["code"] == "validation_error"


def test_health_endpoint(api_client):
    response = api_client.get("/health")

    assert response.status_code == 200
    assert response.data["status"] == "ok"
    assert response.data["database"] == "ok"
