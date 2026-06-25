"""Poll Crestron Home REST API into a shared coordinator snapshot."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .crestron_home_sdk import CrestronHomeApiError, ErrorSource
from .hub import CrestronHub

_LOGGER = logging.getLogger(__name__)


class CrestronDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches rooms, devices, and all controllable/readable endpoints."""

    def __init__(self, hass: HomeAssistant, hub: CrestronHub, entry_id: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry_id}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.hub = hub
        self.config_entry_id = entry_id

    def _fetch_all(self) -> dict[str, Any]:
        c = self.hub.client
        rooms_r = c.get_rooms()
        rooms: dict[int, str] = {r.id: r.name for r in rooms_r.rooms}
        devices = c.get_devices().devices
        lights = c.get_lights().lights
        shades = c.get_shades().shades
        scenes = c.get_scenes().scenes
        thermostats = c.get_thermostats().thermostats
        door_locks = c.get_doorlocks().door_locks
        sensors = c.get_sensors().sensors
        security_devices = c.get_securitydevices().security_devices
        media_rooms = c.get_mediarooms().media_rooms
        quick_actions = c.get_quickactions().quick_actions
        return {
            "rooms": rooms,
            "devices": devices,
            "lights": lights,
            "shades": shades,
            "scenes": scenes,
            "thermostats": thermostats,
            "door_locks": door_locks,
            "sensors": sensors,
            "security_devices": security_devices,
            "media_rooms": media_rooms,
            "quick_actions": quick_actions,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            return self._fetch_all()

        try:
            return await self.hass.async_add_executor_job(_run)
        except CrestronHomeApiError as err:
            if err.error_source == ErrorSource.SESSION_EXPIRED:

                def _relogin() -> dict[str, Any]:
                    self.hub.client.login()
                    return self._fetch_all()

                try:
                    return await self.hass.async_add_executor_job(_relogin)
                except Exception as exc:
                    raise UpdateFailed(f"Session refresh failed: {exc}") from exc
            raise UpdateFailed(f"Crestron API error: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err


def room_prefix(rooms: dict[int, str], room_id: int | None, name: str) -> str:
    """Prefix entity name with room name when available."""
    if room_id is None or room_id not in rooms:
        return name
    return f"{rooms[room_id]} {name}".strip()
