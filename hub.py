"""Crestron Home API session (sync client owned by the integration)."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .crestron_home_sdk import CrestronHomeClient


class CrestronHub:
    """Keeps a logged-in :class:`CrestronHomeClient` for the processor."""

    def __init__(
        self,
        hass: HomeAssistant,
        base_url: str,
        auth_token: str,
        *,
        verify_ssl: bool,
    ) -> None:
        self.hass = hass
        self._client = CrestronHomeClient(
            base_url,
            auth_token=auth_token,
            verify_ssl=verify_ssl,
        )

    @property
    def client(self) -> CrestronHomeClient:
        return self._client

    def connect(self) -> None:
        self._client.login()

    def disconnect(self) -> None:
        try:
            self._client.logout()
        finally:
            self._client.close()
