"""Crestron Home door locks."""

from __future__ import annotations

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CrestronDataUpdateCoordinator
from .entity import CrestronEntity


def _is_locked(status: str | None) -> bool:
    if not status:
        return False
    return status.strip().lower() == "locked"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: CrestronDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    locks = coordinator.data.get("door_locks") or []
    async_add_entities(
        CrestronLock(coordinator, entry, lock.id) for lock in locks
    )


class CrestronLock(CrestronEntity, LockEntity):
    """Lock entity for CWS door locks."""

    def __init__(
        self,
        coordinator: CrestronDataUpdateCoordinator,
        entry: ConfigEntry,
        lock_id: int,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._lock_id = lock_id
        self._attr_unique_id = f"{entry.entry_id}_doorlock_{lock_id}"

    def _lock(self):
        for lock in self.coordinator.data.get("door_locks") or []:
            if lock.id == self._lock_id:
                return lock
        return None

    @property
    def available(self) -> bool:
        return self._lock() is not None

    @property
    def name(self) -> str | None:
        lock = self._lock()
        if not lock:
            return None
        return self._display_name(lock.room_id, lock.name)

    @property
    def is_locked(self) -> bool | None:
        lock = self._lock()
        if not lock:
            return None
        return _is_locked(lock.status)

    @property
    def device_info(self):
        lock = self._lock()
        if not lock:
            return None
        return self._device_info(
            key=f"doorlock_{lock.id}",
            name=self.name or lock.name,
            model=lock.type,
        )

    async def async_lock(self, **kwargs) -> None:
        def _run() -> None:
            self.coordinator.hub.client.doorlocks_lock(self._lock_id)

        await self.hass.async_add_executor_job(_run)
        await self.coordinator.async_request_refresh()

    async def async_unlock(self, **kwargs) -> None:
        def _run() -> None:
            self.coordinator.hub.client.doorlocks_unlock(self._lock_id)

        await self.hass.async_add_executor_job(_run)
        await self.coordinator.async_request_refresh()
