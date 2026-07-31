from rest_framework.routers import SimpleRouter

from books.views import BookViewSet


class OptionalSlashRouter(SimpleRouter):
    """Router that accepts both `/books` and `/books/`.

    Clients (and Postman collections) are inconsistent about the trailing
    slash; accepting both avoids 301 redirects that would drop the POST body.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.trailing_slash = "/?"


router = OptionalSlashRouter()
router.register("books", BookViewSet, basename="book")

urlpatterns = router.urls
