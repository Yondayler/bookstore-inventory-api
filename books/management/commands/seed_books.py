"""Load a small, realistic catalogue so the API can be explored immediately.

    python manage.py seed_books           # add the sample books
    python manage.py seed_books --flush   # wipe the table first
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from books.models import Book

SAMPLE_BOOKS = [
    {
        "title": "El Quijote",
        "author": "Miguel de Cervantes",
        "isbn": "978-84-376-0494-7",
        "cost_usd": Decimal("15.99"),
        "stock_quantity": 25,
        "category": "Literatura Clásica",
        "supplier_country": "ES",
    },
    {
        "title": "Cien Años de Soledad",
        "author": "Gabriel García Márquez",
        "isbn": "9780307474728",
        "cost_usd": Decimal("12.50"),
        "stock_quantity": 8,
        "category": "Realismo Mágico",
        "supplier_country": "CO",
    },
    {
        "title": "Rayuela",
        "author": "Julio Cortázar",
        "isbn": "9788437604947",
        "cost_usd": Decimal("18.75"),
        "stock_quantity": 3,
        "category": "Literatura Clásica",
        "supplier_country": "AR",
    },
    {
        "title": "Clean Code",
        "author": "Robert C. Martin",
        "isbn": "9780132350884",
        "cost_usd": Decimal("42.90"),
        "stock_quantity": 40,
        "category": "Tecnología",
        "supplier_country": "US",
    },
    {
        "title": "La Sombra del Viento",
        "author": "Carlos Ruiz Zafón",
        "isbn": "9780143034902",
        "cost_usd": Decimal("14.25"),
        "stock_quantity": 0,
        "category": "Misterio",
        "supplier_country": "ES",
    },
    {
        "title": "Pedro Páramo",
        "author": "Juan Rulfo",
        "isbn": "8437604737",
        "cost_usd": Decimal("9.99"),
        "stock_quantity": 6,
        "category": "Literatura Clásica",
        "supplier_country": "MX",
    },
]


class Command(BaseCommand):
    help = "Seed the database with sample books."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete every existing book before seeding.",
        )

    def handle(self, *args, **options):
        if options["flush"]:
            deleted, _ = Book.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted} existing rows."))

        created = 0
        for payload in SAMPLE_BOOKS:
            _, was_created = Book.objects.get_or_create(
                isbn_normalized=payload["isbn"].replace("-", ""),
                defaults=payload,
            )
            created += int(was_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: {created} created, "
                f"{len(SAMPLE_BOOKS) - created} already present."
            )
        )
