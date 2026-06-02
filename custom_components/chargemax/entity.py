"""Base entity for ChargeMAX integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL_PREFIX
from .coordinator import ChargeMaxRealtimeCoordinator


class ChargeMaxEntity(CoordinatorEntity[ChargeMaxRealtimeCoordinator]):
    """Base entity for ChargeMAX devices."""

    def __init__(
        self,
        coordinator: ChargeMaxRealtimeCoordinator,
        device_sn: str,
        device_info_data: dict,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device_sn = device_sn
        self._device_info_data = device_info_data
        self._attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        model = self._device_info_data.get("pile_model", "").upper()
        firmware = self._device_info_data.get("firmware_version", 0)

        # Convert firmware version (e.g., 1536 -> "v1.5.36")
        if firmware > 0:
            firmware_str = f"v{firmware // 1000000}.{(firmware // 1000) % 1000}.{firmware % 1000}"
        else:
            firmware_str = "Unknown"

        return DeviceInfo(
            identifiers={(DOMAIN, self._device_sn)},
            name=f"{MODEL_PREFIX} {self._device_sn}",
            manufacturer=MANUFACTURER,
            model=f"{model} ({self._device_info_data.get('rated_power', 0)}W)" if model else None,
            sw_version=firmware_str,
            hw_version=self._device_info_data.get("protocolVersion"),
            configuration_url="https://user.chargingc.com",
        )
