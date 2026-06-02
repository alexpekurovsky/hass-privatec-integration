"""Statistics import for ChargeMAX integration."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMetaData,
    StatisticMeanType,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Storage for tracking last imported timestamps
STORAGE_KEY = f"{DOMAIN}.statistics"
STORAGE_VERSION = 1


async def async_import_charging_history(
    hass: HomeAssistant,
    api: Any,
    device_sn: str,
    device_id: str,
) -> dict[str, Any]:
    """Import individual charging session history into Home Assistant statistics.

    Uses the order list API to fetch individual sessions with exact timestamps.
    Implements early-stop when hitting already-imported data.

    Returns a dict with import results:
    - sessions_imported: number of sessions imported
    - total_energy: total energy imported (kWh)
    - date_range: earliest to latest session
    """
    _LOGGER.info("Starting charging history import for device %s", device_sn)

    # Get the unique statistic ID for this device
    statistic_id = f"{DOMAIN}:{device_sn}_total_energy"

    # Load storage for last imported timestamps
    store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    storage_data = await store.async_load() or {}

    # Check if we have existing statistics
    last_stats = await get_instance(hass).async_add_executor_job(
        get_last_statistics,
        hass,
        1,
        statistic_id,
        True,  # convert_units
        {"sum"},
    )

    # Get the last imported session stop time from storage
    last_timestamp = None
    last_sum = 0

    if device_sn in storage_data:
        last_timestamp_str = storage_data[device_sn].get("last_imported_session_stop")
        if last_timestamp_str:
            last_timestamp = datetime.fromisoformat(last_timestamp_str)
            _LOGGER.info("Found last imported session stop time: %s", last_timestamp)

    if statistic_id in last_stats:
        last_stat = last_stats[statistic_id][0]
        last_sum = last_stat.get("sum", 0)
        _LOGGER.info("Found existing statistics, cumulative sum: %.3f kWh", last_sum)

    if last_timestamp:
        _LOGGER.info("Will only import sessions that ended after %s", last_timestamp)

    # Fetch charging history with pagination and early stop
    new_sessions = []
    page = 1
    stopped_early = False

    while True:
        _LOGGER.debug("Fetching page %d", page)

        history_data = await api.async_get_charging_history(
            evse_id=device_id,
            page=page,
            limit=100,
            state_filter=3,  # All states
        )

        # Parse response - API returns "list" at top level
        records = history_data.get("list", [])

        if not records:
            _LOGGER.debug("No more records on page %d, stopping", page)
            break

        # Process each session
        for record in records:
            evse_order = record.get("evseOrder", {})

            # Get both start and end times for proportional distribution
            start_time = int(evse_order.get("chargeStartTime", 0))
            stop_time = int(evse_order.get("chargeStopTime", 0))

            if start_time == 0 or stop_time == 0:
                continue

            start_dt = datetime.fromtimestamp(start_time, tz=timezone.utc)
            stop_dt = datetime.fromtimestamp(stop_time, tz=timezone.utc)

            # Early stop: if this session ended before our last import, we're done!
            if last_timestamp and stop_dt <= last_timestamp:
                _LOGGER.debug("Hit already-imported session at %s, stopping early", stop_dt)
                stopped_early = True
                break

            # Get total energy for this session
            energy_kwh = evse_order.get("totalElectricity", 0)

            if energy_kwh <= 0:
                continue

            new_sessions.append({
                "start_time": start_time,
                "stop_time": stop_time,
                "start_dt": start_dt,
                "stop_dt": stop_dt,
                "energy": energy_kwh,
            })

        # Check if we should stop
        if stopped_early:
            break

        # Check if there are more pages
        page_reply = history_data.get("pageReply", {})
        total_rows = int(page_reply.get("total_rows", 0))

        if len(new_sessions) >= total_rows or page * 100 >= total_rows:
            _LOGGER.debug("Fetched all available records (%d total)", total_rows)
            break

        page += 1

    if not new_sessions:
        _LOGGER.info("No new sessions to import")
        return {
            "sessions_imported": 0,
            "total_energy": 0,
            "date_range": None,
        }

    # Sort sessions by time (oldest first) for proper statistics
    new_sessions.sort(key=lambda s: s["stop_time"])

    _LOGGER.info("Found %d new sessions to import", len(new_sessions))

    # Distribute energy proportionally across hours for each session
    hourly_sessions = {}

    for session in new_sessions:
        start_dt = session["start_dt"]
        stop_dt = session["stop_dt"]
        total_energy = session["energy"]

        # Calculate total duration in seconds
        duration_seconds = (stop_dt - start_dt).total_seconds()

        if duration_seconds <= 0:
            _LOGGER.warning("Session has invalid duration, skipping")
            continue

        # Energy consumption rate (kWh per second)
        energy_rate = total_energy / duration_seconds

        # Round start time to current hour, round end to next hour
        current_hour = start_dt.replace(minute=0, second=0, microsecond=0)
        end_hour = stop_dt.replace(minute=0, second=0, microsecond=0)

        # If session ended within the same minute as hour boundary, include that hour
        if stop_dt.minute > 0 or stop_dt.second > 0:
            end_hour = end_hour + timedelta(hours=1)

        # Distribute energy across all hours
        while current_hour < end_hour:
            # Calculate the portion of this hour that was used for charging
            hour_start = max(start_dt, current_hour)
            hour_end = min(stop_dt, current_hour + timedelta(hours=1))

            # Calculate seconds of charging in this hour
            charging_seconds = (hour_end - hour_start).total_seconds()

            # Calculate energy for this hour
            hour_energy = energy_rate * charging_seconds

            # Add to hourly totals
            if current_hour not in hourly_sessions:
                hourly_sessions[current_hour] = {
                    "datetime": current_hour,
                    "energy": 0,
                    "count": 0,
                }

            hourly_sessions[current_hour]["energy"] += hour_energy
            hourly_sessions[current_hour]["count"] += 1

            # Move to next hour
            current_hour += timedelta(hours=1)

    # Convert to sorted list
    hourly_data = sorted(hourly_sessions.values(), key=lambda x: x["datetime"])

    _LOGGER.info("Distributed into %d hourly data points", len(hourly_data))

    # Create statistics metadata
    metadata = StatisticMetaData(
        has_mean=False,
        has_sum=True,
        name=f"{device_sn} Total Energy",
        source=DOMAIN,
        statistic_id=statistic_id,
        unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        mean_type=StatisticMeanType.NONE,
        unit_class=None,
    )

    # Convert sessions to statistics
    statistics = []
    cumulative_sum = last_sum  # Start from last known value

    for hour_data in hourly_data:
        cumulative_sum += hour_data["energy"]

        # Create statistic data point
        stat = StatisticData(
            start=hour_data["datetime"],
            sum=cumulative_sum,
            state=hour_data["energy"],  # Energy for this hour
            mean=None,  # We don't track mean values
        )
        statistics.append(stat)

    # Import statistics
    _LOGGER.info("Importing %d charging sessions into statistics", len(statistics))
    await get_instance(hass).async_add_executor_job(
        async_add_external_statistics, hass, metadata, statistics
    )

    # Calculate summary
    total_energy_imported = sum(s["energy"] for s in new_sessions)
    earliest = new_sessions[0]["start_dt"]
    latest = new_sessions[-1]["stop_dt"]

    # Store the last imported session stop time in storage
    storage_data[device_sn] = {
        "last_imported_session_stop": latest.isoformat(),
    }
    await store.async_save(storage_data)
    _LOGGER.info("Stored last imported session stop time: %s", latest)

    result = {
        "sessions_imported": len(statistics),
        "total_energy": total_energy_imported,
        "date_range": f"{earliest.date()} to {latest.date()}",
        "earliest_session": earliest.isoformat(),
        "latest_session": latest.isoformat(),
        "stopped_early": stopped_early,
    }

    _LOGGER.info(
        "Successfully imported %d sessions (%.3f kWh) from %s%s",
        result["sessions_imported"],
        result["total_energy"],
        result["date_range"],
        " (stopped early - all caught up)" if stopped_early else "",
    )

    return result
