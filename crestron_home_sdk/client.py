from __future__ import annotations

from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from .errors import (
    CrestronHomeCommandError,
    CrestronHomePartialCommandError,
    CrestronHomeError,
)
from .http import parse_json, parse_model, raise_for_http_error
from .models import (
    CommandResponse,
    CommandStatus,
    DevicesResponse,
    DoorLocksResponse,
    LightsResponse,
    LightsSetStateRequest,
    LightStateItem,
    LoginResponse,
    MediaPowerState,
    MediaRoomsResponse,
    QuickActionsResponse,
    RoomsResponse,
    ScenesResponse,
    SecurityDevicesResponse,
    SensorsResponse,
    ShadesResponse,
    ShadesSetStateRequest,
    ShadePositionItem,
    ThermostatModeEntry,
    ThermostatSetPointRequest,
    ThermostatSetpointEntry,
    ThermostatsModeRequest,
    ThermostatsResponse,
)

TModel = TypeVar("TModel", bound=BaseModel)

__all__ = ["CrestronHomeClient", "CrestronHomeError"]


class CrestronHomeClient:
    """
    CWS client for the Crestron Home® OS REST API.

    Pass ``base_url`` as the processor root (e.g. ``https://192.168.1.10``) without ``/cws/api``.
    Call :meth:`login` to obtain an AuthKey, then use the resource methods. Use :meth:`logout` to
    end the session.

    ``verify_ssl=False`` is common on LANs when the processor presents a self-signed certificate;
    disabling verification trades MITM protection for connectivity—prefer pinning or a local CA
    where possible.

    For testing, provide ``transport`` (e.g. ``httpx.MockTransport``); it is not used in
    production code paths.
    """

    def __init__(
        self,
        base_url: str,
        *,
        auth_token: str,
        verify_ssl: bool = True,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._auth_token = auth_token
        self._auth_key: str | None = None
        self._client = httpx.Client(
            base_url=f"{self._base}/cws/api",
            verify=verify_ssl,
            timeout=timeout,
            transport=transport,
            headers={"Accept": "application/json"},
        )

    @property
    def api_root(self) -> str:
        return f"{self._base}/cws/api"

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> CrestronHomeClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _auth_headers(self) -> dict[str, str]:
        if not self._auth_key:
            raise CrestronHomeError("Not logged in; call login() first")
        return {"Crestron-RestAPI-AuthKey": self._auth_key}

    def _json_headers(self) -> dict[str, str]:
        h = self._auth_headers()
        h["Content-Type"] = "application/json"
        return h

    def _get_typed(self, path: str, model: type[TModel]) -> TModel:
        r = self._client.get(path, headers=self._auth_headers())
        data = parse_json(r) if r.content else {}
        raise_for_http_error(r, operation=f"GET {path}", body=data)
        return parse_model(data, model, context=f"GET {path}")

    def _post_command(self, path: str, json_body: dict[str, Any] | None = None) -> CommandResponse:
        r = self._client.post(path, headers=self._json_headers(), json=json_body)
        data = parse_json(r) if r.content else {}
        raise_for_http_error(r, operation=f"POST {path}", body=data)
        cmd = parse_model(data, CommandResponse, context=f"POST {path}")
        if cmd.status == CommandStatus.failure:
            raise CrestronHomeCommandError(
                cmd.error_message or "Command failed",
                response=cmd,
                body=data,
            )
        if cmd.status == CommandStatus.partial:
            raise CrestronHomePartialCommandError(
                cmd.error_message or "Partial command result",
                response=cmd,
                body=data,
            )
        return cmd

    def _post_command_empty(self, path: str) -> CommandResponse:
        return self._post_command(path, None)

    # --- Auth ---

    def login(self) -> str:
        """Exchange the web API token for an AuthKey (``GET /login``)."""
        r = self._client.get(
            "/login",
            headers={"Crestron-RestAPI-AuthToken": self._auth_token},
        )
        data = parse_json(r) if r.content else {}
        raise_for_http_error(r, operation="GET /login", body=data)
        lr = parse_model(data, LoginResponse, context="GET /login")
        self._auth_key = lr.auth_key
        return lr.auth_key

    def logout(self) -> None:
        """Invalidate the session (``GET /logout``)."""
        if not self._auth_key:
            return
        self._client.get("/logout", headers=self._auth_headers())
        self._auth_key = None

    # --- Rooms ---

    def get_rooms(self) -> RoomsResponse:
        """``GET /rooms``"""
        return self._get_typed("/rooms", RoomsResponse)

    def get_room(self, room_id: int) -> RoomsResponse:
        """``GET /rooms/{id}``"""
        return self._get_typed(f"/rooms/{room_id}", RoomsResponse)

    # --- Devices ---

    def get_devices(self) -> DevicesResponse:
        """``GET /devices``"""
        return self._get_typed("/devices", DevicesResponse)

    def get_device(self, device_id: int) -> DevicesResponse:
        """``GET /devices/{id}``"""
        return self._get_typed(f"/devices/{device_id}", DevicesResponse)

    # --- Lights ---

    def get_lights(self) -> LightsResponse:
        """``GET /lights``"""
        return self._get_typed("/lights", LightsResponse)

    def get_light(self, light_id: int) -> LightsResponse:
        """``GET /lights/{id}``"""
        return self._get_typed(f"/lights/{light_id}", LightsResponse)

    def lights_set_state(
        self,
        lights: LightsSetStateRequest | list[LightStateItem],
    ) -> CommandResponse:
        """``POST /lights/SetState``"""
        req = lights if isinstance(lights, LightsSetStateRequest) else LightsSetStateRequest(
            lights=lights
        )
        return self._post_command("/lights/SetState", req.model_dump(mode="json"))

    # --- Shades ---

    def get_shades(self) -> ShadesResponse:
        """``GET /shades``"""
        return self._get_typed("/shades", ShadesResponse)

    def get_shade(self, shade_id: int) -> ShadesResponse:
        """``GET /shades/{id}``"""
        return self._get_typed(f"/shades/{shade_id}", ShadesResponse)

    def shades_set_state(
        self,
        shades: ShadesSetStateRequest | list[ShadePositionItem],
    ) -> CommandResponse:
        """``POST /shades/SetState``"""
        req = shades if isinstance(shades, ShadesSetStateRequest) else ShadesSetStateRequest(
            shades=shades
        )
        return self._post_command("/shades/SetState", req.model_dump(mode="json"))

    # --- Scenes ---

    def get_scenes(self) -> ScenesResponse:
        """``GET /scenes``"""
        return self._get_typed("/scenes", ScenesResponse)

    def get_scene(self, scene_id: int) -> ScenesResponse:
        """``GET /scenes/{id}``"""
        return self._get_typed(f"/scenes/{scene_id}", ScenesResponse)

    def recall_scene(self, scene_id: int) -> CommandResponse:
        """``POST /scenes/recall/{id}``"""
        return self._post_command_empty(f"/scenes/recall/{scene_id}")

    # --- Thermostats ---

    def get_thermostats(self) -> ThermostatsResponse:
        """``GET /thermostats``"""
        return self._get_typed("/thermostats", ThermostatsResponse)

    def get_thermostat(self, thermostat_id: int) -> ThermostatsResponse:
        """``GET /thermostats/{id}``"""
        return self._get_typed(f"/thermostats/{thermostat_id}", ThermostatsResponse)

    def thermostats_set_point(self, body: ThermostatSetPointRequest) -> CommandResponse:
        """``POST /thermostats/SetPoint``"""
        return self._post_command("/thermostats/SetPoint", body.model_dump(mode="json"))

    def thermostats_set_point_for(
        self,
        thermostat_id: int,
        setpoints: list[ThermostatSetpointEntry],
    ) -> CommandResponse:
        """Helper: build :class:`ThermostatSetPointRequest` and call :meth:`thermostats_set_point`."""
        return self.thermostats_set_point(
            ThermostatSetPointRequest(id=thermostat_id, setpoints=setpoints)
        )

    def thermostats_set_mode(
        self,
        thermostats: ThermostatsModeRequest | list[ThermostatModeEntry],
    ) -> CommandResponse:
        """``POST /thermostats/mode``"""
        body = (
            thermostats
            if isinstance(thermostats, ThermostatsModeRequest)
            else ThermostatsModeRequest(thermostats=thermostats)
        )
        return self._post_command("/thermostats/mode", body.model_dump(mode="json"))

    def thermostats_set_fan_mode(
        self,
        thermostats: ThermostatsModeRequest | list[ThermostatModeEntry],
    ) -> CommandResponse:
        """``POST /thermostats/fanmode``"""
        body = (
            thermostats
            if isinstance(thermostats, ThermostatsModeRequest)
            else ThermostatsModeRequest(thermostats=thermostats)
        )
        return self._post_command("/thermostats/fanmode", body.model_dump(mode="json"))

    def thermostats_set_schedule(
        self,
        thermostats: ThermostatsModeRequest | list[ThermostatModeEntry],
    ) -> CommandResponse:
        """``POST /thermostats/schedule`` — ``mode`` is ``RUN`` or ``HOLD`` per API manual."""
        body = (
            thermostats
            if isinstance(thermostats, ThermostatsModeRequest)
            else ThermostatsModeRequest(thermostats=thermostats)
        )
        return self._post_command("/thermostats/schedule", body.model_dump(mode="json"))

    # --- Door locks ---

    def get_doorlocks(self) -> DoorLocksResponse:
        """``GET /doorlocks``"""
        return self._get_typed("/doorlocks", DoorLocksResponse)

    def get_doorlock(self, lock_id: int) -> DoorLocksResponse:
        """``GET /doorlocks/{id}``"""
        return self._get_typed(f"/doorlocks/{lock_id}", DoorLocksResponse)

    def doorlocks_lock(self, lock_id: int) -> CommandResponse:
        """``POST /doorlocks/lock/{id}``"""
        return self._post_command_empty(f"/doorlocks/lock/{lock_id}")

    def doorlocks_unlock(self, lock_id: int) -> CommandResponse:
        """``POST /doorlocks/unlock/{id}``"""
        return self._post_command_empty(f"/doorlocks/unlock/{lock_id}")

    # --- Sensors ---

    def get_sensors(self) -> SensorsResponse:
        """``GET /sensors``"""
        return self._get_typed("/sensors", SensorsResponse)

    def get_sensor(self, sensor_id: int) -> SensorsResponse:
        """``GET /sensors/{id}``"""
        return self._get_typed(f"/sensors/{sensor_id}", SensorsResponse)

    # --- Security devices ---

    def get_securitydevices(self) -> SecurityDevicesResponse:
        """``GET /securitydevices``"""
        return self._get_typed("/securitydevices", SecurityDevicesResponse)

    def get_securitydevice(self, device_id: int) -> SecurityDevicesResponse:
        """``GET /securitydevices/{id}``"""
        return self._get_typed(f"/securitydevices/{device_id}", SecurityDevicesResponse)

    # --- Media rooms ---

    def get_mediarooms(self) -> MediaRoomsResponse:
        """``GET /mediarooms``"""
        return self._get_typed("/mediarooms", MediaRoomsResponse)

    def get_mediaroom(self, media_room_id: int) -> MediaRoomsResponse:
        """``GET /mediarooms/{id}``"""
        return self._get_typed(f"/mediarooms/{media_room_id}", MediaRoomsResponse)

    def mediaroom_mute(self, media_room_id: int) -> CommandResponse:
        """``POST /mediarooms/{id}/mute``"""
        return self._post_command_empty(f"/mediarooms/{media_room_id}/mute")

    def mediaroom_unmute(self, media_room_id: int) -> CommandResponse:
        """``POST /mediarooms/{id}/unmute``"""
        return self._post_command_empty(f"/mediarooms/{media_room_id}/unmute")

    def mediaroom_select_source(self, media_room_id: int, source_id: int) -> CommandResponse:
        """``POST /mediarooms/{id}/selectsource/{sid}``"""
        return self._post_command_empty(f"/mediarooms/{media_room_id}/selectsource/{source_id}")

    def mediaroom_set_volume(self, media_room_id: int, level: int) -> CommandResponse:
        """``POST /mediarooms/{id}/volume/{level}`` — ``level`` is 0–100 (percent)."""
        if not 0 <= level <= 100:
            raise CrestronHomeError("Volume level must be between 0 and 100")
        return self._post_command_empty(f"/mediarooms/{media_room_id}/volume/{level}")

    def mediaroom_power(self, media_room_id: int, state: MediaPowerState) -> CommandResponse:
        """``POST /mediarooms/{id}/power/{state}`` — ``state`` is ``on`` or ``off``."""
        return self._post_command_empty(f"/mediarooms/{media_room_id}/power/{state}")

    # --- Quick actions ---

    def get_quickactions(self) -> QuickActionsResponse:
        """``GET /quickactions``"""
        return self._get_typed("/quickactions", QuickActionsResponse)
