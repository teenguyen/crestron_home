"""Crestron Home binary sensors (doors, occupancy)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CrestronDataUpdateCoordinator
from .entity import CrestronEntity


def _door_is_open(status: str | None) -> bool:
    if not status:
        return False
    return "open" in status.strip().lower()


def _presence_is_active(presence: str | None) -> bool:
    if not presence:
        return False
    u = presence.strip().lower()
    if "unoccupied" in u or "vacant" in u or "clear" in u:
        return False
    return "occup" in u or "active" in u or "motion" in u or "detect" in u


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: CrestronDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    sensors = coordinator.data.get("sensors") or []
    entities: list[BinarySensorEntity] = []
    for sensor in sensors:
        if sensor.door_status is not None:
            entities.append(
                CrestronDoorBinarySensor(coordinator, entry, sensor.id),
            )
        elif sensor.presence is not None:
            entities.append(
                CrestronPresenceBinarySensor(coordinator, entry, sensor.id),
            )
    async_add_entities(entities)


class CrestronDoorBinarySensor(CrestronEntity, BinarySensorEntity):
    """Door contact from sensor payload."""

    _attr_device_class = BinarySensorDeviceClass.DOOR

    def __init__(
        self,
        coordinator: CrestronDataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_id: int,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._sensor_id = sensor_id
        self._attr_unique_id = f"{entry.entry_id}_sensor_{sensor_id}_door"

    def _sensor(self):
        for s in self.coordinator.data.get("sensors") or []:
            if s.id == self._sensor_id:
                return s
        return None

    @property
    def available(self) -> bool:
        return self._sensor() is not None

    @property
    def name(self) -> str | None:
        s = self._sensor()
        if not s:
            return None
        base = self._display_name(s.room_id, s.name)
        return f"{base} door"

    @property
    def is_on(self) -> bool | None:
        s = self._sensor()
        if not s:
            return None
        return _door_is_open(s.door_status)

    @property
    def device_info(self):
        s = self._sensor()
        if not s:
            return None
        return self._device_info(
            key=f"sensor_{s.id}_door",
            name=self.name or s.name,
            model=s.sub_type or "Door sensor",
        )


class CrestronPresenceBinarySensor(CrestronEntity, BinarySensorEntity):
    """Occupancy / presence style sensor."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(
        self,
        coordinator: CrestronDataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_id: int,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._sensor_id = sensor_id
        self._attr_unique_id = f"{entry.entry_id}_sensor_{sensor_id}_presence"

    def _sensor(self):
        for s in self.coordinator.data.get("sensors") or []:
            if s.id == self._sensor_id:
                return s
        return None

    @property
    def available(self) -> bool:
        return self._sensor() is not None

    @property
    def name(self) -> str | None:
        s = self._sensor()
        if not s:
            return None
        base = self._display_name(s.room_id, s.name)
        return f"{base} presence"

    @property
    def is_on(self) -> bool | None:
        s = self._sensor()
        if not s:
            return None
        return _presence_is_active(s.presence)

    @property
    def device_info(self):
        s = self._sensor()
        if not s:
            return None
        return self._device_info(
            key=f"sensor_{s.id}_presence",
            name=self.name or s.name,
            model=s.sub_type or "Presence sensor",
        )
