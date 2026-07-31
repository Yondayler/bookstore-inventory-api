import pytest
from django.core.exceptions import ValidationError

from books.validators import has_valid_checksum, normalize_isbn, validate_isbn


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("978-84-376-0494-7", "9788437604947"),
        ("9788437604947", "9788437604947"),
        ("0-306-40615-2", "0306406152"),
        ("043942089x", "043942089X"),
        (" 978 0132350884 ", "9780132350884"),
    ],
)
def test_valid_isbns_are_normalized(raw, expected):
    assert validate_isbn(raw) == expected
    assert normalize_isbn(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "123",
        "12345678901",  # 11 digits
        "978843760494712",  # 15 digits
        "ABC-DEF-GHI",
        "978-84-376-0494-X",  # 'X' is only valid on ISBN-10
    ],
)
def test_invalid_isbns_are_rejected(raw):
    with pytest.raises(ValidationError):
        validate_isbn(raw)


def test_checksum_helper():
    assert has_valid_checksum("9788437604947") is True
    assert has_valid_checksum("9788437604940") is False
    assert has_valid_checksum("0306406152") is True
    assert has_valid_checksum("0306406153") is False


def test_checksum_validation_is_opt_in(settings):
    settings.ISBN_VALIDATE_CHECKSUM = False
    assert validate_isbn("9780000000000") == "9780000000000"

    settings.ISBN_VALIDATE_CHECKSUM = True
    with pytest.raises(ValidationError):
        validate_isbn("9780000000001")
