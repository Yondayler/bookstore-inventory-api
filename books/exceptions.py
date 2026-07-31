from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError


class ExchangeRateUnavailable(APIException):
    """Raised when the provider fails *and* no default rate is configured."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = (
        "The exchange rate provider is unavailable and no fallback rate is "
        "configured for this currency. Please try again later."
    )
    default_code = "exchange_rate_unavailable"


class UnsupportedCurrency(ValidationError):
    """Raised when the requested currency is not quoted by the provider."""

    default_code = "unsupported_currency"
