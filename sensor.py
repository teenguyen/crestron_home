"""Crestron Home sensors (security state, generic levels)."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CrestronDataUpdateCoordinator
from .entity import CrestronEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: CrestronDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    entities: list[SensorEntity] = []

    for dev in coordinator.data.get("security_devices") or []:
        entities.append(CrestronSecuritySensor(coordinator, entry, dev.id))

    for sensor in coordinator.data.get("sensors") or []:
        if sensor.door_status is not None or sensor.presence is not None:
            continue
        if sensor.level is not None:
            entities.append(CrestronLevelSensor(coordinator, entry, sensor.id))
        else:
            entities.append(CrestronGenericSensor(coordinator, entry, sensor.id))

    async_add_entities(entities)


class CrestronSecuritySensor(CrestronEntity, SensorEntity):
    """Security partition / device state as a string."""

    def __init__(
        self,
        coordinator: CrestronDataUpdateCoordinator,
        entry: ConfigEntry,
        device_id: int,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._device_id = device_id
        self._attr_unique_id = f"{entry.entry_id}_security_{device_id}"

    def _dev(self):
        for d in self.coordinator.data.get("security_devices") or []:
            if d.id == self._device_id:
                return d
        return None

    @property
    def available(self) -> bool:
        return self._dev() is not None

    @property
    def name(self) -> str | None:
        d = self._dev()
        if not d:
            return None
        return self._display_name(d.room_id, d.name)

    @property
    def native_value(self) -> str | None:
        d = self._dev()
        if not d:
            return None
        return d.current_state

    @property
    def device_info(self):
        d = self._dev()
        if not d:
            return None
        return self._device_info(
            key=f"security_{d.id}",
            name=self.name or d.name,
            model="Security device",
        )


class CrestronLevelSensor(CrestronEntity, SensorEntity):
    """Numeric level when the CWS sensor exposes ``level``."""

    def __init__(
        self,
        coordinator: CrestronDataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_id: int,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._sensor_id = sensor_id
        self._attr_unique_id = f"{entry.entry_id}_sensor_{sensor_id}_level"

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
        return f"{base} level"

    @property
    def native_value(self) -> int | None:
        s = self._sensor()
        return s.level if s else None

    @property
    def device_info(self):
        s = self._sensor()
        if not s:
            return None
        return self._device_info(
            key=f"sensor_{s.id}_level",
            name=self.name or s.name,
            model=s.sub_type or "Sensor",
        )


class CrestronGenericSensor(CrestronEntity, SensorEntity):
    """Fallback string sensor for CWS sensors without door/presence/level."""

    def __init__(
        self,
        coordinator: CrestronDataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_id: int,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._sensor_id = sensor_id
        self._attr_unique_id = f"{entry.entry_id}_sensor_{sensor_id}_state"

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
        return self._display_name(s.room_id, s.name)

    @property
    def native_value(self) -> str | None:
        s = self._sensor()
        if not s:
            return None
        if s.sub_type:
            return s.sub_type
        return s.name

    @property
    def device_info(self):
        s = self._sensor()
        if not s:
            return None
        return self._device_info(
            key=f"sensor_{s.id}_state",
            name=self.name or s.name,
            model=s.sub_type or "Sensor",
        )
