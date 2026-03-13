"""
PyPress Exception Hierarchy — clean error handling replacing WordPress's WP_Error.
Each exception maps to an HTTP status code.
"""
from typing import Any


class PyPressError(Exception):
    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str = "An error occurred", details: Any = None) -> None:
        self.message = message
        self.details = details
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        result = {"error": self.error_code, "message": self.message, "status": self.status_code}
        if self.details:
            result["details"] = self.details
        return result


# ── 400 Bad Request ──────────────────────────────────────────
class ValidationError(PyPressError):
    status_code = 400
    error_code = "validation_error"

class InvalidParameterError(PyPressError):
    status_code = 400
    error_code = "invalid_parameter"

# ── 401 Unauthorized ─────────────────────────────────────────
class AuthenticationError(PyPressError):
    status_code = 401
    error_code = "authentication_required"

class InvalidTokenError(PyPressError):
    status_code = 401
    error_code = "invalid_token"

class InvalidCredentialsError(PyPressError):
    status_code = 401
    error_code = "invalid_credentials"

# ── 403 Forbidden ────────────────────────────────────────────
class PermissionDeniedError(PyPressError):
    status_code = 403
    error_code = "permission_denied"

class InsufficientCapabilityError(PyPressError):
    status_code = 403
    error_code = "insufficient_capability"

class CSRFValidationError(PyPressError):
    status_code = 403
    error_code = "csrf_validation_failed"

# ── 404 Not Found ────────────────────────────────────────────
class NotFoundError(PyPressError):
    status_code = 404
    error_code = "not_found"

class PostNotFoundError(NotFoundError):
    error_code = "post_not_found"

class UserNotFoundError(NotFoundError):
    error_code = "user_not_found"

# ── 409 Conflict ─────────────────────────────────────────────
class DuplicateError(PyPressError):
    status_code = 409
    error_code = "duplicate"

class SlugConflictError(DuplicateError):
    error_code = "slug_conflict"

# ── 500 Internal ─────────────────────────────────────────────
class PluginError(PyPressError):
    error_code = "plugin_error"

class ThemeError(PyPressError):
    error_code = "theme_error"
