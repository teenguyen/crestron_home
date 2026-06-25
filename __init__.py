"""The Crestron Home integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL, DOMAIN
from .coordinator import CrestronDataUpdateCoordinator
from .hub import CrestronHub

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.LIGHT,
    Platform.COVER,
    Platform.CLIMATE,
    Platform.LOCK,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.MEDIA_PLAYER,
    Platform.SCENE,
]


def _platform_strings() -> list[str]:
    return [p.value for p in PLATFORMS]


async def _async_forward_entry_setups(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Prefer HA's batched helper; older cores only have per-platform setup."""
    forward = getattr(hass, "async_forward_entry_setups", None)
    if forward is not None:
        await forward(entry, PLATFORMS)
        return
    forward_ce = getattr(hass.config_entries, "async_forward_entry_setups", None)
    if forward_ce is not None:
        await forward_ce(entry, PLATFORMS)
        return
    for domain in _platform_strings():
        await hass.config_entries.async_forward_entry_setup(entry, domain)


async def _async_unload_platforms(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload = getattr(hass, "async_unload_platforms", None)
    if unload is not None:
        return await unload(entry, PLATFORMS)
    unload_ce = getattr(hass.config_entries, "async_unload_platforms", None)
    if unload_ce is not None:
        return await unload_ce(entry, PLATFORMS)
    ok = True
    for domain in _platform_strings():
        if not await hass.config_entries.async_forward_entry_unload(entry, domain):
            ok = False
    return ok


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Crestron Home from a config entry."""
    hub = CrestronHub(
        hass,
        entry.data[CONF_URL],
        entry.data[CONF_TOKEN],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
    )
    try:
        await hass.async_add_executor_job(hub.connect)
    except Exception:
        _LOGGER.exception("Failed to connect to Crestron Home")
        await hass.async_add_executor_job(hub.disconnect)
        return False

    coordinator = CrestronDataUpdateCoordinator(hass, hub, entry.entry_id)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "hub": hub,
        "coordinator": coordinator,
    }

    await _async_forward_entry_setups(hass, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await _async_unload_platforms(hass, entry)
    if unload_ok and (data := hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)):
        await hass.async_add_executor_job(data["hub"].disconnect)
    return unload_ok
