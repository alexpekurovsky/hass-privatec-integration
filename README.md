# ChargeMAX EV Charger Integration for Home Assistant

Custom integration for ChargeMAX (PrivateC) EV charging stations.

## Features

- **Real-time Monitoring** (10-second updates):
  - Charging power, voltage, and current (per phase for 3-phase systems)
  - Charging status and duration
  - Session energy consumption
  - State of charge (SOC) when available
  - Current limit setting

- **Statistics** (5-minute updates):
  - Total energy consumption
  - Total charging sessions
  - Total charging time

- **Device Information** (hourly updates):
  - Firmware version
  - IP address
  - Work mode

- **Binary Sensors**:
  - Connection status
  - Cable connected
  - Fault detection
  - Charging active

- **Controls**:
  - Start/stop charging (switch)
  - Adjust current limit (8-32A slider)
  - Change work mode (smart, fast, eco, solar, scheduled)
  - Reboot device
  - Factory reset (disabled by default)

## Installation

### Manual Installation

1. Copy the `custom_components/chargemax` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration
4. Search for "ChargeMAX" and click to add
5. Enter your ChargeMAX account email and password

### HACS Installation (if published)

1. Open HACS
2. Go to Integrations
3. Click the three dots menu → Custom repositories
4. Add this repository URL
5. Search for "ChargeMAX" and install
6. Restart Home Assistant
7. Add the integration via Settings → Devices & Services

## Configuration

The integration is configured through the Home Assistant UI:

1. Go to Settings → Devices & Services
2. Click "Add Integration"
3. Search for "ChargeMAX"
4. Enter your email and password

All devices in your ChargeMAX account will be automatically discovered and added.

## Entities

For each charging station, the following entities are created:

### Sensors (19)
- `sensor.chargemax_SERIAL_power` - Current charging power (W)
- `sensor.chargemax_SERIAL_voltage_l1/l2/l3` - Phase voltages (V)
- `sensor.chargemax_SERIAL_current_l1/l2/l3` - Phase currents (A)
- `sensor.chargemax_SERIAL_session_energy` - Energy in current session (kWh)
- `sensor.chargemax_SERIAL_status` - Charging status
- `sensor.chargemax_SERIAL_charging_duration` - Duration of current session (s)
- `sensor.chargemax_SERIAL_soc` - State of charge (%)
- `sensor.chargemax_SERIAL_current_setting` - Current limit setting (A)
- `sensor.chargemax_SERIAL_last_activity` - Last activity timestamp
- `sensor.chargemax_SERIAL_total_energy` - Lifetime total energy (kWh)
- `sensor.chargemax_SERIAL_total_sessions` - Lifetime session count
- `sensor.chargemax_SERIAL_total_time` - Lifetime charging time (hours)
- `sensor.chargemax_SERIAL_work_mode_sensor` - Current work mode
- `sensor.chargemax_SERIAL_firmware` - Firmware version
- `sensor.chargemax_SERIAL_ip_address` - Device IP address

### Binary Sensors (4)
- `binary_sensor.chargemax_SERIAL_connection` - Online/offline status
- `binary_sensor.chargemax_SERIAL_cable` - Cable connected
- `binary_sensor.chargemax_SERIAL_fault` - Fault detected
- `binary_sensor.chargemax_SERIAL_charging_active` - Currently charging

### Controls
- `switch.chargemax_SERIAL_charging` - Start/stop charging
- `number.chargemax_SERIAL_current_limit` - Adjust current limit (8-32A)
- `select.chargemax_SERIAL_work_mode` - Change work mode
- `button.chargemax_SERIAL_reboot` - Reboot device
- `button.chargemax_SERIAL_reset` - Factory reset (disabled by default)

## Automation Examples

### Start charging when solar production is high

```yaml
automation:
  - alias: "Start EV charging with excess solar"
    trigger:
      - platform: numeric_state
        entity_id: sensor.solar_power
        above: 2000
    condition:
      - condition: state
        entity_id: binary_sensor.chargemax_1325010255_cable
        state: "on"
      - condition: state
        entity_id: switch.chargemax_1325010255_charging
        state: "off"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.chargemax_1325010255_charging
```

### Stop charging when battery is full

```yaml
automation:
  - alias: "Stop charging when EV battery full"
    trigger:
      - platform: numeric_state
        entity_id: sensor.chargemax_1325010255_soc
        above: 80
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.chargemax_1325010255_charging
```

### Adjust current based on home power consumption

```yaml
automation:
  - alias: "Adjust EV charging current based on home load"
    trigger:
      - platform: state
        entity_id: sensor.home_power_consumption
    action:
      - service: number.set_value
        target:
          entity_id: number.chargemax_1325010255_current_limit
        data:
          value: >
            {% set home_load = states('sensor.home_power_consumption') | float %}
            {% set available = 7360 - home_load %}  {# 32A * 230V per phase #}
            {% set current = (available / 230) | round(0) %}
            {{ [8, [current, 32] | min] | max }}
```

## Troubleshooting

### Integration fails to load
- Check Home Assistant logs for errors
- Ensure your credentials are correct
- Verify your ChargeMAX device is online in the mobile app

### Entities not updating
- Check if the device is online (binary_sensor.chargemax_SERIAL_connection)
- Review Home Assistant logs for API errors
- Try reloading the integration

### Authentication errors
- Verify your email and password in the ChargeMAX mobile app
- Re-add the integration with correct credentials

## Known Limitations

- Cloud-based polling (requires internet connection)
- No local API support (device local API is not documented)
- Update intervals are fixed:
  - Real-time data: 10 seconds
  - Statistics: 5 minutes
  - Device info: 1 hour

## Support

For issues and feature requests, please open an issue on GitHub.

## Credits

Reverse engineered from the ChargeMAX Android app (v1.9.3).

## License

This integration is provided as-is without warranty. Use at your own risk.
