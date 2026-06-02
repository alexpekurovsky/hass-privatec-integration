"""Statistics import for ChargeMAX integration."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


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

    # Check if we have existing statistics
    last_stats = await get_instance(hass).async_add_executor_job(
        get_last_statistics,
        hass,
        1,
        statistic_id,
        True,  # convert_units
        {"sum"},
    )

    # Get the last imported timestamp to avoid duplicates
    last_timestamp = None
    last_sum = 0
    if statistic_id in last_stats:
        last_stat = last_stats[statistic_id][0]
        last_timestamp = datetime.fromtimestamp(last_stat["start"], tz=timezone.utc)
        last_sum = last_stat.get("sum", 0)
        _LOGGER.info("Found existing statistics, last import: %s (sum: %.3f kWh)",
                     last_timestamp, last_sum)

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

            # Get session start time (in seconds, not milliseconds)
            start_time = int(evse_order.get("chargeStartTime", 0))
            if start_time == 0:
                continue

            session_dt = datetime.fromtimestamp(start_time, tz=timezone.utc)

            # Early stop: if this session is older than our last import, we're done!
            if last_timestamp and session_dt <= last_timestamp:
                _LOGGER.debug("Hit already-imported session at %s, stopping early", session_dt)
                stopped_early = True
                break

            # This is a new session, add it to import list
            energy_kwh = evse_order.get("totalElectricity", 0)

            new_sessions.append({
                "start_time": start_time,
                "datetime": session_dt,
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
    new_sessions.sort(key=lambda s: s["start_time"])

    _LOGGER.info("Found %d new sessions to import", len(new_sessions))

    # Create statistics metadata
    metadata = StatisticMetaData(
        has_mean=False,
        has_sum=True,
        name=f"{device_sn} Total Energy",
        source=DOMAIN,
        statistic_id=statistic_id,
        unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    )

    # Convert sessions to statistics
    statistics = []
    cumulative_sum = last_sum  # Start from last known value

    for session in new_sessions:
        cumulative_sum += session["energy"]

        # Create statistic data point
        stat = StatisticData(
            start=session["datetime"],
            sum=cumulative_sum,
            state=session["energy"],  # Individual session energy
        )
        statistics.append(stat)

    # Import statistics
    _LOGGER.info("Importing %d charging sessions into statistics", len(statistics))
    async_add_external_statistics(hass, metadata, statistics)

    # Calculate summary
    total_energy_imported = sum(s["energy"] for s in new_sessions)
    earliest = new_sessions[0]["datetime"]
    latest = new_sessions[-1]["datetime"]

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
