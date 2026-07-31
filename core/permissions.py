"""Optional API-key protection for the write endpoints.

The deployed API is public so the evaluation team can exercise it without any
setup, which also means anybody could empty the inventory. Setting the
``API_KEY`` environment variable turns on a key check for every unsafe method
(POST/PUT/PATCH/DELETE) while leaving reads open. With ``API_KEY`` unset — the
default — nothing changes.
"""
import hmac

from django.conf import settings
from rest_framework import exceptions, permissions

SAFE_METHODS = permissions.SAFE_METHODS
HEADER = "X-API-Key"


class WriteRequiresApiKey(permissions.BasePermission):
    message = (
        "This endpoint requires a valid API key. Send it in the 'X-API-Key' header."
    )

    def has_permission(self, request, view):
        expected = getattr(settings, "API_KEY", "")
        if not expected or request.method in SAFE_METHODS:
            return True

        provided = request.headers.get(HEADER, "")
        # Constant-time comparison so the key cannot be guessed by timing.
        if provided and hmac.compare_digest(str(provided), str(expected)):
            return True

        # Raised rather than returned so the client gets a "permission denied"
        # explaining the header, instead of DRF's generic "credentials were not
        # provided" coming from the session authenticator.
        raise exceptions.PermissionDenied(self.message)
