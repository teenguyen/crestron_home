"""Crestron Home media rooms."""

from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CrestronDataUpdateCoordinator
from .entity import CrestronEntity


def _parse_sources(sources: Any) -> tuple[list[str], dict[str, int]]:
    """Build source labels and name -> source id for select_source."""
    labels: list[str] = []
    name_to_id: dict[str, int] = {}
    if not sources or not isinstance(sources, list):
        return labels, name_to_id
    for item in sources:
        if isinstance(item, dict):
            sid = item.get("id") if "id" in item else item.get("sourceId")
            name = item.get("name") or item.get("label")
            if sid is not None:
                sid_int = int(sid)
                label = str(name) if name is not None else str(sid_int)
                labels.append(label)
                name_to_id[label] = sid_int
        elif isinstance(item, str):
            labels.append(item)
    return labels, name_to_id


def _muted(state: str | None) -> bool:
    if not state:
        return False
    u = state.strip().lower()
    if u in ("muted", "on", "true", "yes"):
        return True
    return "mute" in u and "off" not in u


def _power_on(state: str | None) -> bool:
    if not state:
        return False
    return state.strip().lower() == "on"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: CrestronDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    rooms = coordinator.data.get("media_rooms") or []
    async_add_entities(
        CrestronMediaPlayer(coordinator, entry, mr.id) for mr in rooms
    )


class CrestronMediaPlayer(CrestronEntity, MediaPlayerEntity):
    """Media room: volume, mute, power, source."""

    def __init__(
        self,
        coordinator: CrestronDataUpdateCoordinator,
        entry: ConfigEntry,
        media_room_id: int,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._mr_id = media_room_id
        self._attr_unique_id = f"{entry.entry_id}_mediaroom_{media_room_id}"

    def _mr(self):
        for mr in self.coordinator.data.get("media_rooms") or []:
            if mr.id == self._mr_id:
                return mr
        return None

    @property
    def available(self) -> bool:
        return self._mr() is not None

    @property
    def name(self) -> str | None:
        mr = self._mr()
        if not mr:
            return None
        return self._display_name(mr.room_id, mr.name)

    @property
    def device_info(self):
        mr = self._mr()
        if not mr:
            return None
        return self._device_info(
            key=f"mediaroom_{mr.id}",
            name=self.name or mr.name,
            model="Media room",
        )

    @property
    def state(self) -> str | None:
        mr = self._mr()
        if not mr:
            return None
        if mr.current_power_state and not _power_on(mr.current_power_state):
            return STATE_OFF
        return STATE_ON

    @property
    def volume_level(self) -> float | None:
        mr = self._mr()
        if not mr or mr.current_volume_level is None:
            return None
        return max(0.0, min(1.0, mr.current_volume_level / 100.0))

    @property
    def is_volume_muted(self) -> bool | None:
        mr = self._mr()
        if not mr:
            return None
        return _muted(mr.current_mute_state)

    @property
    def source(self) -> str | None:
        mr = self._mr()
        if not mr or mr.current_source_id is None:
            return None
        labels, name_to_id = _parse_sources(mr.available_sources)
        for label, sid in name_to_id.items():
            if sid == mr.current_source_id:
                return label
        return str(mr.current_source_id)

    @property
    def source_list(self) -> list[str] | None:
        mr = self._mr()
        if not mr:
            return None
        labels, _ = _parse_sources(mr.available_sources)
        return labels if labels else None

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        mr = self._mr()
        feats = (
            MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
        )
        if mr and mr.available_sources:
            _, m = _parse_sources(mr.available_sources)
            if m:
                feats |= MediaPlayerEntityFeature.SELECT_SOURCE
        return feats

    async def async_turn_on(self) -> None:
        def _run() -> None:
            self.coordinator.hub.client.mediaroom_power(self._mr_id, "on")

        await self.hass.async_add_executor_job(_run)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        def _run() -> None:
            self.coordinator.hub.client.mediaroom_power(self._mr_id, "off")

        await self.hass.async_add_executor_job(_run)
        await self.coordinator.async_request_refresh()

    async def async_mute_volume(self, mute: bool) -> None:
        def _run() -> None:
            if mute:
                self.coordinator.hub.client.mediaroom_mute(self._mr_id)
            else:
                self.coordinator.hub.client.mediaroom_unmute(self._mr_id)

        await self.hass.async_add_executor_job(_run)
        await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        level = max(0, min(100, round(volume * 100)))

        def _run() -> None:
            self.coordinator.hub.client.mediaroom_set_volume(self._mr_id, int(level))

        await self.hass.async_add_executor_job(_run)
        await self.coordinator.async_request_refresh()

    async def async_select_source(self, source: str) -> None:
        mr = self._mr()
        if not mr:
            return
        _, name_to_id = _parse_sources(mr.available_sources)
        sid = name_to_id.get(source)
        if sid is None:
            return

        def _run() -> None:
            self.coordinator.hub.client.mediaroom_select_source(self._mr_id, sid)

        await self.hass.async_add_executor_job(_run)
        await self.coordinator.async_request_refresh()
