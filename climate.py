"""Crestron Home thermostats."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import CrestronDataUpdateCoordinator
from .crestron_home_sdk.models import ThermostatModeEntry, ThermostatSetpointEntry
from .entity import CrestronEntity


# Crestron thermostat temperatures are integers in tenths of a degree
# (e.g. 770 = 77.0°, 590 = 59.0°), regardless of the temperatureUnits
# granularity (FahrenheitWholeDegrees / CelsiusWholeDegrees / CelsiusHalfDegrees).
TEMP_SCALE = 10


def _api_temp_to_native(value: int | str | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            return None
    return value / TEMP_SCALE


def _native_temp_to_api(value: float) -> int:
    return int(round(value * TEMP_SCALE))


def _api_hvac_to_ha(mode: str | None) -> HVACMode:
    if not mode:
        return HVACMode.UNKNOWN
    u = mode.strip().upper()
    if "OFF" in u:
        return HVACMode.OFF
    if "HEAT" in u:
        return HVACMode.HEAT
    if "COOL" in u:
        return HVACMode.COOL
    if "AUTO" in u and "HEAT" not in u and "COOL" not in u:
        return HVACMode.AUTO
    if "FAN" in u and "HEAT" not in u and "COOL" not in u:
        return HVACMode.FAN_ONLY
    if "AUTO" in u:
        return HVACMode.HEAT_COOL
    return HVACMode.HEAT_COOL


def _pick_api_mode(available: list[str] | None, hvac: HVACMode) -> str | None:
    if not available:
        return None
    want = hvac.name.upper()
    for m in available:
        if m.strip().upper() == want:
            return m
    for m in available:
        mu = m.upper()
        if hvac == HVACMode.OFF and "OFF" in mu:
            return m
        if hvac == HVACMode.HEAT and "HEAT" in mu:
            return m
        if hvac == HVACMode.COOL and "COOL" in mu:
            return m
        if hvac == HVACMode.AUTO and "AUTO" in mu:
            return m
        if hvac == HVACMode.FAN_ONLY and "FAN" in mu:
            return m
    return available[0]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: CrestronDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    thermostats = coordinator.data.get("thermostats") or []
    async_add_entities(
        CrestronClimate(coordinator, entry, t.id) for t in thermostats
    )


class CrestronClimate(CrestronEntity, ClimateEntity):
    """Climate entity backed by CWS thermostats."""

    def __init__(
        self,
        coordinator: CrestronDataUpdateCoordinator,
        entry: ConfigEntry,
        thermostat_id: int,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._tid = thermostat_id
        self._attr_unique_id = f"{entry.entry_id}_thermostat_{thermostat_id}"

    def _t(self):
        for th in self.coordinator.data.get("thermostats") or []:
            if th.id == self._tid:
                return th
        return None

    @property
    def available(self) -> bool:
        return self._t() is not None

    @property
    def name(self) -> str | None:
        th = self._t()
        if not th:
            return None
        return self._display_name(th.room_id, th.name)

    @property
    def device_info(self):
        th = self._t()
        if not th:
            return None
        return self._device_info(
            key=f"thermostat_{th.id}",
            name=self.name or th.name,
            model=th.mode,
        )

    @property
    def supported_features(self) -> ClimateEntityFeature:
        feats = ClimateEntityFeature.TARGET_TEMPERATURE
        th = self._t()
        if th and th.available_fan_modes:
            feats |= ClimateEntityFeature.FAN_MODE
        return feats

    @property
    def hvac_modes(self) -> list[HVACMode]:
        th = self._t()
        if not th or not th.available_system_modes:
            return [HVACMode.OFF]
        modes = [
            m
            for m in (_api_hvac_to_ha(x) for x in th.available_system_modes)
            if m != HVACMode.UNKNOWN
        ]
        modes = list(dict.fromkeys(modes))
        return modes if modes else [HVACMode.OFF]

    @property
    def hvac_mode(self) -> HVACMode:
        th = self._t()
        return _api_hvac_to_ha(th.mode if th else None)

    @property
    def fan_modes(self) -> list[str] | None:
        th = self._t()
        if not th or not th.available_fan_modes:
            return None
        return list(th.available_fan_modes)

    @property
    def fan_mode(self) -> str | None:
        th = self._t()
        return th.current_fan_mode if th else None

    @property
    def native_temperature(self) -> float | None:
        th = self._t()
        if not th:
            return None
        v = th.current_temperature if th.current_temperature is not None else th.temperature
        return _api_temp_to_native(v)

    @property
    def target_temperature(self) -> float | None:
        th = self._t()
        if not th or not th.set_point or th.set_point.temperature is None:
            return None
        return _api_temp_to_native(th.set_point.temperature)

    @property
    def min_temp(self) -> float:
        th = self._t()
        if th and th.set_point and th.set_point.min_value is not None:
            v = _api_temp_to_native(th.set_point.min_value)
            if v is not None:
                return v
        if self._native_unit() == UnitOfTemperature.FAHRENHEIT:
            return 45.0
        return 7.0

    @property
    def max_temp(self) -> float:
        th = self._t()
        if th and th.set_point and th.set_point.max_value is not None:
            v = _api_temp_to_native(th.set_point.max_value)
            if v is not None:
                return v
        if self._native_unit() == UnitOfTemperature.FAHRENHEIT:
            return 95.0
        return 35.0

    def _native_unit(self) -> str:
        th = self._t()
        # e.g. "FahrenheitWholeDegrees"; match the full word so "CelsiusHalfDegrees"
        # (which contains an "f") is not misread as Fahrenheit.
        if th and th.temperature_units and "FAHRENHEIT" in th.temperature_units.upper():
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def native_temperature_unit(self) -> str:
        return self._native_unit()

    @property
    def target_temperature_step(self) -> float:
        th = self._t()
        if th and th.temperature_units and "HALF" in th.temperature_units.upper():
            return 0.5
        return 1.0

    @property
    def precision(self) -> float:
        return self.target_temperature_step

    def _setpoint_type_for_mode(self, th) -> str:
        hvac = _api_hvac_to_ha(th.mode)
        if hvac == HVACMode.COOL:
            return "cool"
        if hvac == HVACMode.HEAT:
            return "heat"
        if th.set_point and th.set_point.type:
            return th.set_point.type.lower()
        if th.available_set_points:
            return (th.available_set_points[0].type or "heat").lower()
        return "heat"

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        th = self._t()
        if not th:
            return
        sp_type = self._setpoint_type_for_mode(th)
        t_int = _native_temp_to_api(float(temp))

        def _set() -> None:
            self.coordinator.hub.client.thermostats_set_point_for(
                self._tid,
                [ThermostatSetpointEntry(type=sp_type, temperature=t_int)],
            )

        await self.hass.async_add_executor_job(_set)
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        th = self._t()
        if not th:
            return
        api_mode = _pick_api_mode(th.available_system_modes, hvac_mode)
        if not api_mode:
            return

        def _set() -> None:
            self.coordinator.hub.client.thermostats_set_mode(
                [ThermostatModeEntry(id=self._tid, mode=api_mode)]
            )

        await self.hass.async_add_executor_job(_set)
        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        th = self._t()
        if not th or not th.available_fan_modes:
            return

        def _set() -> None:
            self.coordinator.hub.client.thermostats_set_fan_mode(
                [ThermostatModeEntry(id=self._tid, mode=fan_mode)]
            )

        await self.hass.async_add_executor_job(_set)
        await self.coordinator.async_request_refresh()
