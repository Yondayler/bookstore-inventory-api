"""ISBN parsing and validation helpers.

Business rule: "isbn debe tener formato válido (10 o 13 dígitos)".

Hyphens and spaces are accepted on input (that is how ISBNs are printed on a
book cover) but the digits-only form is what uniqueness is enforced on, so
``978-84-376-0494-7`` and ``9788437604947`` are recognised as the same book.
"""
import re

from django.conf import settings
from django.core.exceptions import ValidationError

ISBN_ALLOWED_CHARS = re.compile(r"^[0-9Xx\- ]+$")


def normalize_isbn(value: str) -> str:
    """Strip hyphens/spaces and upper-case the ISBN-10 check character."""
    if value is None:
        return ""
    return re.sub(r"[\s\-]", "", str(value)).upper()


def isbn10_check_digit(digits: str) -> str:
    total = sum((10 - index) * int(char) for index, char in enumerate(digits[:9]))
    remainder = (11 - (total % 11)) % 11
    return "X" if remainder == 10 else str(remainder)


def isbn13_check_digit(digits: str) -> str:
    total = sum(
        int(char) * (1 if index % 2 == 0 else 3) for index, char in enumerate(digits[:12])
    )
    return str((10 - (total % 10)) % 10)


def has_valid_checksum(normalized: str) -> bool:
    if len(normalized) == 10:
        return normalized[9] == isbn10_check_digit(normalized)
    if len(normalized) == 13:
        return normalized[12] == isbn13_check_digit(normalized)
    return False


def validate_isbn(value: str) -> str:
    """Validate an ISBN and return its normalized (digits-only) form.

    Raises ``django.core.exceptions.ValidationError`` with a human readable
    message, which DRF surfaces as a 400 response.
    """
    raw = "" if value is None else str(value).strip()
    if not raw:
        raise ValidationError("ISBN is required.")

    if not ISBN_ALLOWED_CHARS.match(raw):
        raise ValidationError(
            "ISBN may only contain digits, hyphens, spaces and a trailing 'X'."
        )

    normalized = normalize_isbn(raw)

    if len(normalized) not in (10, 13):
        raise ValidationError(
            f"ISBN must contain 10 or 13 digits, got {len(normalized)}: '{raw}'."
        )

    body, check = normalized[:-1], normalized[-1]
    if not body.isdigit():
        raise ValidationError("ISBN must contain only digits (except the check digit).")
    if len(normalized) == 13 and not normalized.isdigit():
        raise ValidationError("A 13-digit ISBN must contain only digits.")
    if len(normalized) == 10 and not (check.isdigit() or check == "X"):
        raise ValidationError("The check digit of an ISBN-10 must be a digit or 'X'.")

    if getattr(settings, "ISBN_VALIDATE_CHECKSUM", False) and not has_valid_checksum(
        normalized
    ):
        raise ValidationError(f"'{raw}' has an invalid ISBN check digit.")

    return normalized
