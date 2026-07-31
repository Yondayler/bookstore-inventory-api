"""Consistent JSON error envelope for every failure the API can produce.

Every error — validation (400), missing resource (404), unreachable exchange
rate provider (503) or an unexpected crash (500) — is rendered as:

    {
      "error": {
        "code": "validation_error",
        "message": "The request contains invalid data.",
        "details": {"isbn": ["ISBN must contain 10 or 13 digits."]}
      },
      "status_code": 400
    }
"""
import logging

from django.http import JsonResponse
from rest_framework import exceptions as drf_exceptions
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

DEFAULT_MESSAGES = {
    400: "The request contains invalid data.",
    401: "Authentication credentials were not provided or are invalid.",
    403: "You do not have permission to perform this action.",
    404: "The requested resource was not found.",
    405: "Method not allowed for this endpoint.",
    409: "The request conflicts with the current state of the resource.",
    415: "Unsupported media type.",
    429: "Too many requests. Please slow down.",
    500: "An unexpected error occurred. Please try again later.",
    503: "An upstream service is unavailable. Please try again later.",
}

STATUS_CODES = {
    400: "validation_error",
    401: "not_authenticated",
    403: "permission_denied",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    415: "unsupported_media_type",
    429: "throttled",
    500: "internal_server_error",
    503: "service_unavailable",
}


def error_payload(status_code, message=None, code=None, details=None):
    payload = {
        "error": {
            "code": code or STATUS_CODES.get(status_code, "error"),
            "message": message or DEFAULT_MESSAGES.get(status_code, "Unexpected error."),
        },
        "status_code": status_code,
    }
    if details:
        payload["error"]["details"] = details
    return payload


def api_exception_handler(exc, context):
    """DRF exception handler that normalises every response body."""
    response = drf_exception_handler(exc, context)

    if response is None:
        # Not a DRF exception: log it and return a JSON 500 instead of the
        # default HTML error page.
        logger.exception("Unhandled exception in %s", context.get("view"))
        from rest_framework.response import Response

        return Response(error_payload(500), status=500)

    status_code = response.status_code
    detail = response.data
    code = getattr(exc, "default_code", None) or STATUS_CODES.get(status_code, "error")
    message = DEFAULT_MESSAGES.get(status_code)
    details = None

    if isinstance(detail, dict):
        if set(detail.keys()) == {"detail"}:
            message = str(detail["detail"])
        else:
            details = detail
    elif isinstance(detail, list):
        details = {"non_field_errors": detail}
    elif detail is not None:
        message = str(detail)

    if isinstance(exc, drf_exceptions.ValidationError):
        code = "validation_error"
        message = DEFAULT_MESSAGES[400]

    response.data = error_payload(status_code, message=message, code=code, details=details)
    return response


# --- Django-level handlers (requests that never reach a DRF view) -----------


def bad_request(request, exception=None):
    return JsonResponse(error_payload(400), status=400)


def page_not_found(request, exception=None):
    return JsonResponse(
        error_payload(404, message=f"No endpoint matches the path '{request.path}'."),
        status=404,
    )


def server_error(request):
    return JsonResponse(error_payload(500), status=500)
