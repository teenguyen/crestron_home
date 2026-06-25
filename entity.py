"""Shared entity helpers."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import CrestronDataUpdateCoordinator, room_prefix


class CrestronEntity(CoordinatorEntity[CrestronDataUpdateCoordinator]):
    """Base for entities bound to the Crestron coordinator."""

    _attr_has_entity_name = False

    def __init__(self, coordinator: CrestronDataUpdateCoordinator) -> None:
        super().__init__(coordinator)

    def _device_info(
        self,
        *,
        key: str,
        name: str,
        model: str | None = None,
    ) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.coordinator.config_entry_id}_{key}")},
            name=name,
            manufacturer=MANUFACTURER,
            model=model,
        )

    def _display_name(self, room_id: int | None, item_name: str) -> str:
        rooms: dict[int, str] = self.coordinator.data.get("rooms", {})
        return room_prefix(rooms, room_id, item_name)
