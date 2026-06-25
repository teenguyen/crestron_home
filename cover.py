"""Crestron Home shades."""

from __future__ import annotations

from typing import Any

from homeassistant.components.cover import CoverDeviceClass, CoverEntity, CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CrestronDataUpdateCoordinator
from .crestron_home_sdk.models import ShadePositionItem
from .entity import CrestronEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: CrestronDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    shades = coordinator.data.get("shades") or []
    async_add_entities(
        CrestronShadeCover(coordinator, entry, shade.id) for shade in shades
    )


class CrestronShadeCover(CrestronEntity, CoverEntity):
    """Shade / blind with position 0–100."""

    _attr_device_class = CoverDeviceClass.SHADE
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(
        self,
        coordinator: CrestronDataUpdateCoordinator,
        entry: ConfigEntry,
        shade_id: int,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._shade_id = shade_id
        self._attr_unique_id = f"{entry.entry_id}_shade_{shade_id}"

    def _shade(self):
        for shade in self.coordinator.data.get("shades") or []:
            if shade.id == self._shade_id:
                return shade
        return None

    @property
    def available(self) -> bool:
        return self._shade() is not None

    @property
    def name(self) -> str | None:
        s = self._shade()
        if not s:
            return None
        return self._display_name(s.room_id, s.name)

    @property
    def current_cover_position(self) -> int | None:
        s = self._shade()
        if not s or s.position is None:
            return None
        return max(0, min(100, s.position))

    @property
    def is_closed(self) -> bool | None:
        pos = self.current_cover_position
        if pos is None:
            return None
        return pos <= 0

    @property
    def device_info(self):
        s = self._shade()
        if not s:
            return None
        return self._device_info(
            key=f"shade_{s.id}",
            name=self.name or s.name,
            model=s.sub_type,
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self._async_set_position(100)

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self._async_set_position(0)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        position = kwargs.get("position")
        if position is None:
            return
        await self._async_set_position(int(position))

    async def _async_set_position(self, position: int) -> None:
        pos = max(0, min(100, position))

        def _set() -> None:
            self.coordinator.hub.client.shades_set_state(
                [ShadePositionItem(id=self._shade_id, position=pos)]
            )

        await self.hass.async_add_executor_job(_set)
        await self.coordinator.async_request_refresh()
