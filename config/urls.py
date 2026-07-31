from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from core.views import api_root, health_check

urlpatterns = [
    path("", api_root, name="api-root"),
    path("health", health_check, name="health-check"),
    path("health/", health_check),
    path("admin/", admin.site.urls),
    # Business endpoints are exposed at the root (POST /books, GET /books/{id}, ...)
    path("", include("books.urls")),
    # OpenAPI schema + interactive docs
    path("api/schema", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

handler400 = "core.exception_handler.bad_request"
handler404 = "core.exception_handler.page_not_found"
handler500 = "core.exception_handler.server_error"
