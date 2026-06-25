from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class CommandStatus(str, Enum):
    success = "success"
    partial = "partial"
    failure = "failure"


class CommandResponse(BaseModel):
    """Typical JSON body for POST control endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    status: CommandStatus
    version: str | None = None
    error_message: str | None = Field(None, alias="errorMessage")
    error_devices: list[int] | None = Field(None, alias="errorDevices")


class LoginResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    auth_key: str = Field(validation_alias=AliasChoices("AuthKey", "authKey", "authkey"))


# --- Rooms ---


class Room(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    name: str


class RoomsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    rooms: list[Room]
    version: str | None = None


# --- Devices (generic index) ---


class GenericDevice(BaseModel):
    """Device index entry; some firmware builds omit ``name`` / ``type`` (loads report ``level`` only)."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: int
    name: str = ""
    type: str = ""
    sub_type: str | None = Field(None, alias="subType")
    room_id: int | None = Field(None, validation_alias=AliasChoices("roomId", "roomid"))
    level: int | None = None
    connection_status: str | None = Field(None, alias="connectionStatus")


class DevicesResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    devices: list[GenericDevice]
    version: str | None = None


# --- Lights ---


class Light(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: int
    name: str
    type: str
    sub_type: str | None = Field(None, alias="subType")
    level: int | None = None
    connection_status: str | None = Field(None, alias="connectionStatus")
    room_id: int | None = Field(None, validation_alias=AliasChoices("roomId", "roomid"))


class LightsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    lights: list[Light]
    version: str | None = None


class LightStateItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    level: int
    time: int


class LightsSetStateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    lights: list[LightStateItem]


# --- Shades ---


class Shade(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: int
    name: str
    sub_type: str | None = Field(None, alias="subType")
    position: int | None = None
    connection_status: str | None = Field(None, alias="connectionStatus")
    room_id: int | None = Field(None, validation_alias=AliasChoices("roomId", "roomid"))


class ShadesResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    shades: list[Shade]
    version: str | None = None


class ShadePositionItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    position: int


class ShadesSetStateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    shades: list[ShadePositionItem]


# --- Scenes ---


class Scene(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: int
    name: str
    type: str
    status: bool | str | None = None
    room_id: int | None = Field(None, validation_alias=AliasChoices("roomId", "roomid"))


class ScenesResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    scenes: list[Scene]
    version: str | None = None


# --- Thermostats ---


class ThermostatSetpointInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    type: str
    temperature: int | None = None
    min_value: int | None = Field(None, alias="minValue")
    max_value: int | None = Field(None, alias="maxValue")


class Thermostat(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: int
    name: str
    # Firmware reports the active mode as "currentMode"; older docs used "mode".
    mode: str | None = Field(None, validation_alias=AliasChoices("currentMode", "mode"))
    # Firmware reports "currentSetPoint" as an ARRAY of setpoints (one per active
    # type; when off, a single entry with no temperature). Older docs showed a
    # single "setPoint" object, so either form is normalized to a list below.
    current_set_point: list[ThermostatSetpointInfo] | None = Field(
        None, validation_alias=AliasChoices("currentSetPoint", "setPoint")
    )
    current_temperature: int | None = Field(None, alias="currentTemperature")
    temperature: int | None = None
    temperature_units: str | None = Field(None, alias="temperatureUnits")
    current_fan_mode: str | None = Field(None, alias="currentFanMode")
    scheduler_state: str | None = Field(None, alias="schedulerState")
    available_fan_modes: list[str] | None = Field(None, alias="availableFanModes")
    available_system_modes: list[str] | None = Field(None, alias="availableSystemModes")
    available_set_points: list[ThermostatSetpointInfo] | None = Field(None, alias="availableSetPoints")
    connection_status: str | None = Field(None, alias="connectionStatus")
    room_id: int | None = Field(None, validation_alias=AliasChoices("roomId", "roomid"))

    @field_validator("current_set_point", mode="before")
    @classmethod
    def _normalize_set_point(cls, v: Any) -> Any:
        # Accept either a single object (older docs) or a list (firmware).
        if isinstance(v, dict):
            return [v]
        return v

    @property
    def set_point(self) -> ThermostatSetpointInfo | None:
        """The active setpoint, enriched with min/max from availableSetPoints.

        ``currentSetPoint`` entries carry only ``type``/``temperature`` (and when
        the thermostat is off, no temperature at all); the min/max bounds live in
        ``availableSetPoints`` for the matching type.
        """
        entries = self.current_set_point or []
        active = next((sp for sp in entries if sp.temperature is not None), None)
        if active is None and entries:
            active = entries[0]
        if active is None:
            return None
        min_value = active.min_value
        max_value = active.max_value
        if (min_value is None or max_value is None) and self.available_set_points:
            for avail in self.available_set_points:
                if avail.type and active.type and avail.type.lower() == active.type.lower():
                    if min_value is None:
                        min_value = avail.min_value
                    if max_value is None:
                        max_value = avail.max_value
                    break
        return ThermostatSetpointInfo(
            type=active.type,
            temperature=active.temperature,
            min_value=min_value,
            max_value=max_value,
        )


class ThermostatsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    thermostats: list[Thermostat]
    version: str | None = None


class ThermostatSetpointEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: str
    temperature: int | str | None = None


class ThermostatSetPointRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    setpoints: list[ThermostatSetpointEntry]


class ThermostatModeEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    mode: str


class ThermostatsModeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    thermostats: list[ThermostatModeEntry]


# --- Door locks ---


class DoorLock(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: int
    name: str
    type: str | None = None
    status: str | None = None
    connection_status: str | None = Field(None, alias="connectionStatus")
    room_id: int | None = Field(None, validation_alias=AliasChoices("roomId", "roomid"))


class DoorLocksResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    door_locks: list[DoorLock] = Field(validation_alias=AliasChoices("doorLocks", "doorlocks"))


# --- Sensors (variant payloads; unknown keys preserved via extra) ---


class Sensor(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: int
    name: str
    sub_type: str | None = Field(None, alias="subType")
    room_id: int | None = Field(None, validation_alias=AliasChoices("roomId", "roomid"))
    presence: str | None = None
    level: int | None = None
    connection_status: str | None = Field(None, alias="connectionStatus")
    door_status: str | None = Field(None, alias="door status")
    battery_level: str | None = Field(None, alias="battery level")


class SensorsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sensors: list[Sensor]
    version: str | None = None


# --- Security devices ---


class SecurityDevice(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: int
    name: str
    available_states: list[str] | None = Field(None, alias="availableStates")
    current_state: str | None = Field(None, alias="currentState")
    connection_status: str | None = Field(None, alias="connectionStatus")
    room_id: int | None = Field(None, validation_alias=AliasChoices("roomId", "roomid"))


class SecurityDevicesResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    security_devices: list[SecurityDevice] = Field(
        validation_alias=AliasChoices("securityDevices", "securitydevices")
    )
    version: str | None = None


# --- Media rooms ---


class MediaRoom(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: int
    name: str
    room_id: int | None = Field(None, validation_alias=AliasChoices("roomId", "roomid"))
    current_volume_level: int | None = Field(None, alias="currentVolumeLevel")
    current_mute_state: str | None = Field(None, alias="currentMuteState")
    current_power_state: str | None = Field(None, alias="currentPowerState")
    current_provider_id: int | None = Field(None, alias="currentProviderId")
    current_source_id: int | None = Field(None, alias="currentSourceId")
    available_providers: list[str] | None = Field(None, alias="availableProviders")
    available_sources: list[Any] | None = Field(None, alias="availableSources")
    available_volume_controls: list[str] | None = Field(None, alias="availableVolumeControls")
    available_mute_controls: list[str] | None = Field(None, alias="availableMuteControls")
    available_power_states: list[str] | None = Field(None, alias="availablePowerStates")
    scheduler_state: str | None = Field(None, alias="schedulerState")
    available_fan_modes: list[str] | None = Field(None, alias="availableFanModes")
    available_system_modes: list[str] | None = Field(None, alias="availableSystemModes")
    available_set_points: list[Any] | None = Field(None, alias="availableSetPoints")


class MediaRoomsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    media_rooms: list[MediaRoom] = Field(validation_alias=AliasChoices("mediaRooms", "mediarooms"))
    version: str | None = None


# --- Quick actions ---


class QuickAction(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    name: str


class QuickActionsResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    quick_actions: list[QuickAction] = Field(
        validation_alias=AliasChoices("quickActions", "quickactions")
    )
    version: str | None = None


MediaPowerState = Literal["on", "off"]
