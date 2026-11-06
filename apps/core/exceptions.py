from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """Custom exception handler that returns Vietnamese error messages."""
    response = exception_handler(exc, context)

    if response is not None:
        custom_data = {
            "error": True,
            "code": getattr(exc, "default_code", "error"),
            "detail": response.data,
        }
        if hasattr(exc, "error_code"):
            custom_data["code"] = exc.error_code
        response.data = custom_data

    return response


class BusinessError(Exception):
    """Raised by service layer for business rule violations."""
    def __init__(self, message: str, error_code: str, status_code: int = 409):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(message)

    def to_response(self):
        return Response(
            {"error": True, "code": self.error_code, "message": self.message},
            status=self.status_code,
        )
