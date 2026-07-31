"""Create the table backing the shared exchange-rate cache.

`createcachetable` is normally a management command, but running it from a
migration means the table exists in every environment (production, CI and the
test database) without an extra deployment step.
"""
from django.core.management import call_command
from django.db import migrations

TABLE_NAME = "exchange_rate_cache"


def create_cache_table(apps, schema_editor):
    call_command(
        "createcachetable",
        TABLE_NAME,
        database=schema_editor.connection.alias,
        verbosity=0,
    )


def drop_cache_table(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f'DROP TABLE IF EXISTS "{TABLE_NAME}"')


class Migration(migrations.Migration):
    dependencies = [("books", "0001_initial")]

    operations = [migrations.RunPython(create_cache_table, drop_cache_table)]
