"""Crestron Home lights."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CrestronDataUpdateCoordinator
from .crestron_home_sdk.models import LightStateItem
from .entity import CrestronEntity


def _level_to_brightness(level: int | None) -> int | None:
    if level is None:
        return None
    return max(0, min(255, round(level * 255 / 100)))


def _brightness_to_level(brightness: int) -> int:
    return max(0, min(100, round(brightness * 100 / 255)))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: CrestronDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    lights = coordinator.data.get("lights") or []
    async_add_entities(
        CrestronLight(coordinator, entry, light.id) for light in lights
    )


class CrestronLight(CrestronEntity, LightEntity):
    """Light controlled via CWS SetState."""

    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(
        self,
        coordinator: CrestronDataUpdateCoordinator,
        entry: ConfigEntry,
        light_id: int,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._light_id = light_id
        self._attr_unique_id = f"{entry.entry_id}_light_{light_id}"

    def _find_light(self):
        for light in self.coordinator.data.get("lights") or []:
            if light.id == self._light_id:
                return light
        return None

    @property
    def _light(self):
        return self._find_light()

    @property
    def available(self) -> bool:
        return self._light is not None

    @property
    def name(self) -> str | None:
        light = self._light
        if not light:
            return None
        return self._display_name(light.room_id, light.name)

    @property
    def is_on(self) -> bool | None:
        light = self._light
        if not light or light.level is None:
            return None
        return light.level > 0

    @property
    def brightness(self) -> int | None:
        light = self._light
        if not light:
            return None
        return _level_to_brightness(light.level)

    @property
    def device_info(self):
        light = self._light
        if not light:
            return None
        return self._device_info(
            key=f"light_{light.id}",
            name=self.name or light.name,
            model=light.type,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is not None:
            level = _brightness_to_level(int(brightness))
        else:
            prev = self._light
            level = prev.level if prev and prev.level else 100

        def _set() -> None:
            self.coordinator.hub.client.lights_set_state(
                [LightStateItem(id=self._light_id, level=level, time=0)]
            )

        await self.hass.async_add_executor_job(_set)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        def _set() -> None:
            self.coordinator.hub.client.lights_set_state(
                [LightStateItem(id=self._light_id, level=0, time=0)]
            )

        await self.hass.async_add_executor_job(_set)
        await self.coordinator.async_request_refresh()
