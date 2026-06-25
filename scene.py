"""Crestron Home scenes (recall via HA scene entities)."""

from __future__ import annotations

from typing import Any

import homeassistant.components.scene as _ha_scene

# HA 2025+ exposes ``Scene``; older cores used ``SceneEntity``. Resolve at runtime so we
# never run ``from ... import SceneEntity`` (fails on current HA when missing).
SceneBase = getattr(_ha_scene, "Scene", None) or getattr(_ha_scene, "SceneEntity", None)
if SceneBase is None:
    msg = "homeassistant.components.scene has neither Scene nor SceneEntity"
    raise ImportError(msg)

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
    scenes = coordinator.data.get("scenes") or []
    async_add_entities(
        CrestronSceneEntity(coordinator, entry, scene.id) for scene in scenes
    )


class CrestronSceneEntity(CrestronEntity, SceneBase):
    """Activates a Crestron scene via POST /scenes/recall/{id}."""

    def __init__(
        self,
        coordinator: CrestronDataUpdateCoordinator,
        entry: ConfigEntry,
        scene_id: int,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._scene_id = scene_id
        self._attr_unique_id = f"{entry.entry_id}_scene_{scene_id}"

    def _scene(self):
        for sc in self.coordinator.data.get("scenes") or []:
            if sc.id == self._scene_id:
                return sc
        return None

    @property
    def available(self) -> bool:
        return self._scene() is not None

    @property
    def name(self) -> str | None:
        sc = self._scene()
        if not sc:
            return None
        return self._display_name(sc.room_id, sc.name)

    @property
    def device_info(self):
        sc = self._scene()
        if not sc:
            return None
        return self._device_info(
            key=f"scene_{sc.id}",
            name=self.name or sc.name,
            model=sc.type,
        )

    async def async_activate(self, **kwargs: Any) -> None:
        def _run() -> None:
            self.coordinator.hub.client.recall_scene(self._scene_id)

        await self.hass.async_add_executor_job(_run)
        await self.coordinator.async_request_refresh()
