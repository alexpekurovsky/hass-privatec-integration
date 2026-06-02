# Energy Dashboard Integration Guide

This guide explains how your ChargeMAX charging data is automatically imported into Home Assistant and how to add it to the Energy dashboard.

## Automatic Import (No Setup Required!)

The ChargeMAX integration **automatically imports your charging history**:

- **On first setup:** Imports all historical charging sessions (30 seconds after Home Assistant starts)
- **Every hour:** Checks for new charging sessions and imports them
- **Smart early-stop:** Only fetches what's needed, stops when caught up
- **Session-level detail:** Each charging session is imported individually with exact timestamps

### What Gets Imported

Each charging session is distributed proportionally across hours:

- Energy is spread based on actual charging time in each hour
- Example: 10:30-13:30 charging 3 kWh:
  - 10:00 hour → 0.5 kWh (30 min of 60)
  - 11:00 hour → 1.0 kWh (full hour)
  - 12:00 hour → 1.0 kWh (full hour)
  - 13:00 hour → 0.5 kWh (30 min of 60)
- Multiple sessions in the same hour are combined
- Energy totals preserved exactly

This gives you **accurate hourly granularity** in the Energy dashboard:

- View realistic hourly consumption patterns
- See daily totals with correct distribution
- Track energy usage across time accurately

## Step 1: Add to Energy Dashboard

Once the integration is set up (history imports automatically):

1. Go to **Settings** → **Dashboards** → **Energy**
2. Click **Add Consumption**
3. Select: `sensor.chargemax_SERIAL_total_energy`
   (Replace SERIAL with your device serial number, e.g., `1325010255`)
4. Click **Save**

## Step 2: Verify Historical Data

1. Go to the **Energy** dashboard
2. Use the date picker to view historical periods
3. You should see your imported charging data in the graphs

The energy dashboard will show:
- Daily charging consumption
- Monthly totals
- Yearly totals
- Comparison between periods

## Ongoing Tracking

After the initial import, the integration will automatically:
- Update the total energy every 5 minutes from the API
- Home Assistant will calculate statistics for the Energy dashboard
- New charging sessions will be reflected in the dashboard

## Re-importing Data

If you need to import data again (e.g., after restoring Home Assistant):

1. The import service is **idempotent** - it won't create duplicates
2. It tracks the last imported timestamp
3. Only new sessions since the last import will be added
4. Safe to run multiple times

## Automations with Energy Data

You can use the energy sensor in automations:

### Example: Notify when monthly charging exceeds threshold

```yaml
automation:
  - alias: "High EV charging cost alert"
    trigger:
      - platform: time
        at: "23:59:00"
    condition:
      - condition: template
        value_template: >
          {% set energy = states('sensor.chargemax_1325010255_total_energy') | float %}
          {% set last_month = states.sensor.chargemax_1325010255_total_energy.last_changed.month %}
          {{ energy > 200 and now().month != last_month }}
    action:
      - service: notify.notify
        data:
          message: "EV charged {{ energy }} kWh this month"
```

## Troubleshooting

### No data showing in Energy dashboard

1. **Check the sensor value:**
   - Go to **Developer Tools** → **States**
   - Find `sensor.chargemax_SERIAL_total_energy`
   - Verify it has a value and `state_class: total_increasing`

2. **Check statistics were imported:**
   - Go to **Developer Tools** → **Statistics**
   - Search for `chargemax:SERIAL_total_energy`
   - Verify you see historical data points

3. **Check recorder:**
   - Ensure recorder integration is working
   - Check `config/home-assistant.log` for errors

### Statistics not showing correct values

1. **Re-run import:**
   ```yaml
   service: chargemax.import_history
   target:
     device_id: YOUR_DEVICE_ID
   ```

2. **Check import logs:**
   Look for messages like:
   ```
   Importing charging history for device ...
   Successfully imported 179 sessions (1045.685 kWh)
   ```

### Historical data before integration installation

The `import_history` service fetches **all** charging sessions from your ChargeMAX account, regardless of when they occurred. This means:

- If you've been using your charger for 2 years, all sessions will be imported
- The API provides complete charging history
- Statistics will be backdated to the actual session timestamps

## Advanced: Manual Statistics Inspection

To inspect the imported statistics using SQL (for advanced users):

```bash
sqlite3 /config/home-assistant_v2.db

SELECT
  datetime(start_ts, 'unixepoch', 'localtime') as date,
  sum
FROM statistics
JOIN statistics_meta ON statistics.metadata_id = statistics_meta.id
WHERE statistics_meta.statistic_id = 'chargemax:1325010255_total_energy'
ORDER BY start_ts DESC
LIMIT 10;
```

## Energy Dashboard Features

Once integrated, you can use Energy dashboard features like:

- **Cost tracking**: Add electricity costs to see charging expenses
- **Grid return**: Track solar offset if you have solar panels
- **Gas comparison**: Compare EV charging vs. gasoline costs
- **Device comparison**: Compare charger energy to other devices
- **Carbon footprint**: See CO2 impact based on your grid mix

## Example Energy Dashboard Configuration

Complete energy dashboard configuration with ChargeMAX:

```yaml
# configuration.yaml
energy:
  sources:
    - type: grid
      grid_consumption:
        - entity_id: sensor.grid_consumption
      grid_return:
        - entity_id: sensor.grid_return
    - type: solar
      solar:
        - entity_id: sensor.solar_production
  devices:
    - entity_id: sensor.chargemax_1325010255_total_energy
      name: "EV Charger"
      unit_of_measurement: "kWh"
```

That's it! Your ChargeMAX charging history is now fully integrated with Home Assistant's Energy dashboard. 🎉
