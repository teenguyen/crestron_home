from __future__ import annotations

import json
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from .errors import CrestronHomeApiError, CrestronHomeError

T = TypeVar("T", bound=BaseModel)


def parse_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except json.JSONDecodeError as e:
        raise CrestronHomeError(
            f"Invalid JSON in response: {e}",
            status_code=response.status_code,
            body=response.text,
        ) from e


def parse_error_source(body: Any) -> int | None:
    if not isinstance(body, dict):
        return None
    raw = body.get("errorSource")
    if raw is None:
        raw = body.get("error_source")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return None


def raise_for_http_error(
    response: httpx.Response,
    *,
    operation: str,
    body: Any,
) -> None:
    if response.status_code == httpx.codes.OK:
        return
    err_src = parse_error_source(body)
    msg = None
    if isinstance(body, dict):
        msg = body.get("errorMessage") or body.get("message")
    if not msg and isinstance(body, str):
        msg = body
    if not msg:
        msg = response.text or f"HTTP {response.status_code}"
    message = f"{operation} failed: {msg}"
    if err_src is not None:
        message = f"{operation} failed (errorSource={err_src}): {msg}"
        raise CrestronHomeApiError(
            message,
            status_code=response.status_code,
            body=body,
            error_source=err_src,
        )
    raise CrestronHomeError(message, status_code=response.status_code, body=body)


def parse_model(data: Any, model: type[T], *, context: str) -> T:
    try:
        return model.model_validate(data)
    except ValidationError as e:
        raise CrestronHomeError(f"{context}: invalid payload: {e}", body=data) from e
