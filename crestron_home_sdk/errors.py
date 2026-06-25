from __future__ import annotations

from enum import IntEnum
from typing import Any

from .models import CommandResponse


class ErrorSource(IntEnum):
    """Documented ``errorSource`` values from the Crestron Home JSON payload reference."""

    SESSION_EXPIRED = 5001
    AUTHENTICATION = 5002
    ROOMS = 6001
    UNHANDLED = 7000
    LOGIN = 7001
    LIGHTS = 7003
    SHADES = 7004
    LOGOUT = 7005
    SCENES = 7006
    THERMOSTATS = 7007
    FAN_MODE = 7008
    SYSTEM_MODE = 7009
    INVALID_DATA = 8000
    DEVICES = 8001
    SECURITY_DEVICES = 8005
    SENSORS = 8006
    DOOR_LOCKS = 8007
    SCHEDULER = 8008
    SETPOINT = 8009
    MEDIA_ROOMS = 8010


class CrestronHomeError(Exception):
    """Raised when the API returns an error or an unexpected response."""

    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class CrestronHomeApiError(CrestronHomeError):
    """HTTP or JSON error that includes an ``errorSource`` code when present."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        body: Any = None,
        error_source: int | None = None,
    ) -> None:
        super().__init__(message, status_code=status_code, body=body)
        self.error_source = error_source


class CrestronHomeCommandError(CrestronHomeError):
    """POST command completed with ``status: failure`` in the JSON body (HTTP 200)."""

    def __init__(self, message: str, *, response: CommandResponse, body: Any = None) -> None:
        super().__init__(message, status_code=200, body=body)
        self.response = response


class CrestronHomePartialCommandError(CrestronHomeCommandError):
    """POST command completed with ``status: partial`` in the JSON body (HTTP 200)."""
