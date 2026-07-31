"""Optional API-key protection and OpenAPI schema shape."""
import pytest

pytestmark = pytest.mark.django_db


# --- optional write protection ---------------------------------------------


def test_writes_are_open_when_no_api_key_is_configured(api_client, book_payload, settings):
    settings.API_KEY = ""
    assert api_client.post("/books", book_payload, format="json").status_code == 201


def test_writes_require_the_key_when_configured(api_client, book_payload, settings):
    settings.API_KEY = "s3cr3t"

    denied = api_client.post("/books", book_payload, format="json")
    assert denied.status_code == 403
    assert denied.data["error"]["code"] == "permission_denied"

    wrong = api_client.post(
        "/books", book_payload, format="json", headers={"X-API-Key": "nope"}
    )
    assert wrong.status_code == 403

    allowed = api_client.post(
        "/books", book_payload, format="json", headers={"X-API-Key": "s3cr3t"}
    )
    assert allowed.status_code == 201


def test_reads_stay_public_even_with_a_key_configured(api_client, book, settings):
    settings.API_KEY = "s3cr3t"

    assert api_client.get("/books").status_code == 200
    assert api_client.get(f"/books/{book.id}").status_code == 200
    assert api_client.get("/books/low-stock").status_code == 200


def test_delete_is_protected_by_the_key(api_client, book, settings):
    settings.API_KEY = "s3cr3t"

    assert api_client.delete(f"/books/{book.id}").status_code == 403
    assert (
        api_client.delete(
            f"/books/{book.id}", headers={"X-API-Key": "s3cr3t"}
        ).status_code
        == 204
    )


def test_calculate_price_is_protected_by_the_key(api_client, book, settings):
    settings.API_KEY = "s3cr3t"

    response = api_client.post(f"/books/{book.id}/calculate-price", {}, format="json")
    assert response.status_code == 403


# --- error messages ---------------------------------------------------------


def test_404_message_names_the_book(api_client):
    response = api_client.get("/books/4242")

    assert response.status_code == 404
    assert response.data["error"]["message"] == "Book with id 4242 was not found."


# --- OpenAPI schema ---------------------------------------------------------


def test_schema_documents_paths_without_a_trailing_slash(api_client):
    response = api_client.get("/api/schema?format=json")

    assert response.status_code == 200
    paths = set(response.data["paths"].keys())
    assert "/books" in paths
    assert "/books/{id}" in paths
    assert "/books/{id}/calculate-price" in paths
    assert "/books/low-stock" in paths
    assert "/books/search" in paths
    assert not any(path.endswith("/") for path in paths)


def test_docs_are_served(api_client):
    assert api_client.get("/api/docs").status_code == 200
