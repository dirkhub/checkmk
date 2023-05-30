#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

# EXAMPLE DATA FROM: WDC SSC-D0128SC-2100
# <<<smart>>>
# /dev/sda ATA WDC_SSC-D0128SC-   1 Raw_Read_Error_Rate     0x000b   100   100   050    Pre-fail  Always       -       16777215
# /dev/sda ATA WDC_SSC-D0128SC-   3 Spin_Up_Time            0x0007   100   100   050    Pre-fail  Always       -       0
# /dev/sda ATA WDC_SSC-D0128SC-   5 Reallocated_Sector_Ct   0x0013   100   100   050    Pre-fail  Always       -       0
# /dev/sda ATA WDC_SSC-D0128SC-   7 Seek_Error_Rate         0x000b   100   100   050    Pre-fail  Always       -       0
# /dev/sda ATA WDC_SSC-D0128SC-   9 Power_On_Hours          0x0012   100   100   000    Old_age   Always       -       1408
# /dev/sda ATA WDC_SSC-D0128SC-  10 Spin_Retry_Count        0x0013   100   100   050    Pre-fail  Always       -       0
# /dev/sda ATA WDC_SSC-D0128SC-  12 Power_Cycle_Count       0x0012   100   100   000    Old_age   Always       -       523
# /dev/sda ATA WDC_SSC-D0128SC- 168 Unknown_Attribute       0x0012   100   100   000    Old_age   Always       -       1
# /dev/sda ATA WDC_SSC-D0128SC- 175 Program_Fail_Count_Chip 0x0003   100   100   010    Pre-fail  Always       -       0
# /dev/sda ATA WDC_SSC-D0128SC- 192 Power-Off_Retract_Count 0x0012   100   100   000    Old_age   Always       -       0
# /dev/sda ATA WDC_SSC-D0128SC- 194 Temperature_Celsius     0x0022   040   100   000    Old_age   Always       -       40 (Lifetime Min/Max 30/60)
# /dev/sda ATA WDC_SSC-D0128SC- 197 Current_Pending_Sector  0x0012   100   100   000    Old_age   Always       -       0
# /dev/sda ATA WDC_SSC-D0128SC- 240 Head_Flying_Hours       0x0013   100   100   050    Pre-fail  Always       -       0
# /dev/sda ATA WDC_SSC-D0128SC- 170 Unknown_Attribute       0x0003   100   100   010    Pre-fail  Always       -       1769478
# /dev/sda ATA WDC_SSC-D0128SC- 173 Unknown_Attribute       0x0012   100   100   000    Old_age   Always       -       4217788040605
import time
from collections.abc import Callable, Iterable, Mapping, MutableMapping, Sequence
from enum import Enum
from typing import Any, Final, NamedTuple

from .agent_based_api.v1 import (
    get_rate,
    get_value_store,
    Metric,
    register,
    render,
    Result,
    Service,
    State,
)
from .agent_based_api.v1.type_defs import CheckResult, DiscoveryResult, StringTable

Section = Mapping[str, Mapping[str, int]]

Disk = MutableMapping[str, int]
Disks = MutableMapping[str, Disk]


class DiskAttributeItem(NamedTuple):
    name: str
    capture_on_discovery: bool
    renderer: Callable[[int], str]


class DiskAttribute(DiskAttributeItem, Enum):
    REALLOCATED_SECTORS = DiskAttributeItem("Reallocated_Sectors", True, str)
    POWER_ON_HOURS = DiskAttributeItem("Power_On_Hours", False, lambda h: render.timespan(h * 3600))
    SPIN_RETRIES = DiskAttributeItem("Spin_Retries", True, str)
    POWER_CYCLES = DiskAttributeItem("Power_Cycles", False, str)
    END_TO_END_ERRORS = DiskAttributeItem("End-to-End_Errors", True, str)
    UNCORRECTABLE_ERRORS = DiskAttributeItem("Uncorrectable_Errors", True, str)
    COMMAND_TIMEOUT_COUNTER = DiskAttributeItem("Command_Timeout_Counter", True, str)
    TEMPERATURE = DiskAttributeItem("Temperature", False, str)
    REALLOCATED_EVENTS = DiskAttributeItem("Reallocated_Events", True, str)
    PENDING_SECTORS = DiskAttributeItem("Pending_Sectors", True, str)
    UDMA_CRC_ERRORS = DiskAttributeItem("UDMA_CRC_Errors", True, str)
    CRC_ERRORS = DiskAttributeItem("CRC_Errors", True, str)
    CRITICAL_WARNING = DiskAttributeItem("Critical_Warning", True, str)
    MEDIA_AND_DATA_INTEGRITY_ERRORS = DiskAttributeItem(
        "Media_and_Data_Integrity_Errors", True, str
    )
    AVAILABLE_SPARE = DiskAttributeItem("Available_Spare", False, render.percent)
    PERCENTAGE_USED = DiskAttributeItem("Percentage_Used", False, render.percent)
    ERROR_INFORMATION_LOG_ENTRIES = DiskAttributeItem("Error_Information_Log_Entries", False, str)
    DATA_UNITS_READ = DiskAttributeItem("Data_Units_Read", False, render.bytes)
    DATA_UNITS_WRITTEN = DiskAttributeItem("Data_Units_Written", False, render.bytes)


# The command timeouts is a counter and we experienced that on some devices, it will already be
# increased by one count after a simple reboot. In a faulty situation it will however increase in
# much larger steps (100 or 1000). So we accept any rate below 100 counts per hour.
# See CMK-7684
MAX_COMMAND_TIMEOUTS_PER_HOUR = 100

CRC_ERRORS_ID: Final = 199

# This mapping also limits the used ATA attributes.
# All ATA attributes not listed here will be discarded when parsing the raw agent section
ATA_ID_TO_DISK_ATTRIBUTE: Final[Mapping[int, DiskAttribute]] = {
    5: DiskAttribute.REALLOCATED_SECTORS,
    9: DiskAttribute.POWER_ON_HOURS,
    10: DiskAttribute.SPIN_RETRIES,
    12: DiskAttribute.POWER_CYCLES,
    184: DiskAttribute.END_TO_END_ERRORS,
    187: DiskAttribute.UNCORRECTABLE_ERRORS,
    188: DiskAttribute.COMMAND_TIMEOUT_COUNTER,
    194: DiskAttribute.TEMPERATURE,
    196: DiskAttribute.REALLOCATED_EVENTS,
    197: DiskAttribute.PENDING_SECTORS,
    CRC_ERRORS_ID: DiskAttribute.CRC_ERRORS,
}


def _set_int_or_zero(disk: Disk, key: str, value: Any) -> None:
    try:
        disk[key] = int(value)
    except ValueError:
        disk[key] = 0


def parse_raw_values(string_table: StringTable) -> Section:
    """
    >>> from pprint import pprint
    >>> pprint(parse_raw_values([
    ...     ['/dev/sda', 'ATA', 'WDC_SSC-D0128SC-', '1', 'Raw_Read_Error_Rate',
    ...      '0x000b', '100', '100', '050', 'Pre-fail', 'Always', '-', '16777215'],
    ...     ['/dev/sda', 'ATA', 'WDC_SSC-D0128SC-', '3', 'Spin_Up_Time',
    ...      '0x0007', '100', '100', '050', 'Pre-fail', 'Always', '-', '0'],
    ...     ['/dev/sda', 'ATA', 'WDC_SSC-D0128SC-', '5', 'Reallocated_Sector_Ct',
    ...      '0x0013', '100', '100', '050', 'Pre-fail', 'Always', '-', '0'],
    ...     ['/dev/sda', 'ATA', 'WDC_SSC-D0128SC-', '7', 'Seek_Error_Rate',
    ...      '0x000b', '100', '100', '050', 'Pre-fail', 'Always', '-', '0'],
    ...     ['/dev/sda', 'ATA', 'WDC_SSC-D0128SC-', '9', 'Power_On_Hours',
    ...      '0x0012', '100', '100', '000', 'Old_age', 'Always', '-', '1408'],
    ...     ['/dev/sda', 'ATA', 'WDC_SSC-D0128SC-', '10', 'Spin_Retry_Count',
    ...      '0x0013', '100', '100', '050', 'Pre-fail', 'Always', '-', '0'],
    ...     ['/dev/sda', 'ATA', 'WDC_SSC-D0128SC-', '12', 'Power_Cycle_Count',
    ...      '0x0012', '100', '100', '000', 'Old_age', 'Always', '-', '523'],
    ...     ['/dev/sda', 'ATA', 'WDC_SSC-D0128SC-', '168', 'Unknown_Attribute',
    ...      '0x0012', '100', '100', '000', 'Old_age', 'Always', '-', '1'],
    ...     ['/dev/sda', 'ATA', 'WDC_SSC-D0128SC-', '175', 'Program_Fail_Count_Chip',
    ...      '0x0003', '100', '100', '010', 'Pre-fail', 'Always', '-', '0'],
    ...     ['/dev/sda', 'ATA', 'WDC_SSC-D0128SC-', '192', 'Power-Off_Retract_Count',
    ...      '0x0012', '100', '100', '000', 'Old_age', 'Always', '-', '0'],
    ...     ['/dev/sda', 'ATA', 'WDC_SSC-D0128SC-', '194', 'Temperature_Celsius',
    ...      '0x0022', '040', '100', '000', 'Old_age', 'Always', '-', '40', '(Lifetime', 'Min/Max', '30/60)'],
    ...     ['/dev/sda', 'ATA', 'WDC_SSC-D0128SC-', '197', 'Current_Pending_Sector',
    ...      '0x0012', '100', '100', '000', 'Old_age', 'Always', '-', '0'],
    ...     ['/dev/sda', 'ATA', 'WDC_SSC-D0128SC-', '240', 'Head_Flying_Hours',
    ...      '0x0013', '100', '100', '050', 'Pre-fail', 'Always', '-', '0'],
    ...     ['/dev/sda', 'ATA', 'WDC_SSC-D0128SC-', '170', 'Unknown_Attribute',
    ...      '0x0003', '100', '100', '010', 'Pre-fail', 'Always', '-', '1769478'],
    ...     ['/dev/sda', 'ATA', 'WDC_SSC-D0128SC-', '173', 'Unknown_Attribute',
    ...      '0x0012', '100', '100', '000', 'Old_age', 'Always', '-', '4217788040605'],
    ... ]))
    {'/dev/sda': {'Head_Flying_Hours': 0,
                  'Pending_Sectors': 0,
                  'Power-Off_Retract_Count': 0,
                  'Power_Cycles': 523,
                  'Power_On_Hours': 1408,
                  'Program_Fail_Count_Chip': 0,
                  'Raw_Read_Error_Rate': 16777215,
                  'Reallocated_Sectors': 0,
                  'Seek_Error_Rate': 0,
                  'Spin_Retries': 0,
                  'Spin_Up_Time': 0,
                  'Temperature': 40}}

    """
    ata_lines = (line for line in string_table if len(line) >= 13)
    nvme_lines = (line for line in string_table if 3 <= len(line) <= 6)

    return {**_parse_ata_lines(ata_lines), **_parse_nvme_lines(nvme_lines)}


def _parse_ata_lines(ata_lines: Iterable[Sequence[str]]) -> Section:
    ata_disks: MutableMapping[str, Disk] = {}

    for (
        disk_path,
        _disk_type,
        _disk_name,
        ID,
        attribute_name,
        _flag,
        value,
        _worst,
        threshold,
        _type,
        _updated,
        _when_failed,
        raw_value,
        *_raw_value_info,
    ) in ata_lines:
        disk = ata_disks.setdefault(disk_path, {})

        if attribute_name == "Unknown_Attribute":
            continue

        if int(ID) == CRC_ERRORS_ID and attribute_name == "UDMA_CRC_Error_Count":
            # UDMA_CRC_Error_Count and CRC_Error_Count share the same attribute ID (199).
            # Since we explicitly distinguish between the two, we choose "UDMA_CRC_Error_Count"
            # whenever the ID 199 comes with this textual information.
            # Otherwise, we default to CRC_Error_Count.
            _set_int_or_zero(disk, DiskAttribute.UDMA_CRC_ERRORS.name, raw_value)
            continue

        if (lookup_attribute := ATA_ID_TO_DISK_ATTRIBUTE.get(int(ID))) is None:
            if attribute_name in disk:
                # Don't override already set attributes
                continue
            _set_int_or_zero(disk, attribute_name, raw_value)
            continue

        _set_int_or_zero(disk, lookup_attribute.name, raw_value)

        if lookup_attribute is DiskAttribute.REALLOCATED_EVENTS:
            # special case, see check function
            try:
                disk["_normalized_value_Reallocated_Events"] = int(value)
                disk["_normalized_threshold_Reallocated_Events"] = int(threshold)
            except ValueError:
                pass

    return ata_disks


def _parse_nvme_lines(nvme_lines: Iterable[Sequence[str]]) -> Section:
    nvme_disks: MutableMapping[str, Disk] = {}

    for line in nvme_lines:
        if "/dev" in line[0]:
            disk = nvme_disks.setdefault(line[0], {})
            continue

        field, value = [e.strip() for e in " ".join(line).split(":")]
        key = field.replace(" ", "_")
        value = value.replace("%", "").replace(".", "").replace(",", "")
        match field:
            case "Temperature":
                _set_int_or_zero(disk, key, value.split()[0])
            case "Critical Warning":
                disk[key] = int(value, 16)
            case "Data Units Read":
                disk[key] = int(value.split()[0]) * 512000
            case "Data Units Written":
                disk[key] = int(value.split()[0]) * 512000
            case _:
                _set_int_or_zero(disk, key, value)

    return nvme_disks


register.agent_section(
    name="smart",
    parse_function=parse_raw_values,
)


def discover_smart_stats(section: Section) -> DiscoveryResult:
    for disk_name, disk in section.items():
        captured = {
            f.name: disk[f.name] for f in DiskAttribute if f.capture_on_discovery and f.name in disk
        }
        if captured:
            yield Service(item=disk_name, parameters=captured)


def check_smart_stats(item: str, params: Mapping[str, int], section: Section) -> CheckResult:
    # params is a snapshot of all counters at the point of time of inventory
    disk = section.get(item)
    if disk is None:
        return

    for attribute in DiskAttribute:
        if attribute is DiskAttribute.TEMPERATURE:
            # Currently handled by separate check
            continue

        value = disk.get(attribute.name)
        if value is None:
            continue
        assert isinstance(value, int)

        infotext = "%s: %s" % (_display_attribute_name(attribute), attribute.renderer(value))

        ref_value = params.get(attribute.name)

        if attribute is DiskAttribute.AVAILABLE_SPARE:
            ref_value = disk["Available_Spare_Threshold"]

        if ref_value is None:
            yield Result(state=State.OK, summary=infotext)
            yield Metric(attribute.name, value)
            continue

        if attribute is DiskAttribute.AVAILABLE_SPARE:
            state = State.CRIT if value < ref_value else State.OK
        else:
            state = State.CRIT if value > ref_value else State.OK
        hints = [] if state == State.OK else ["during discovery: %d (!!)" % ref_value]

        # For reallocated event counts we experienced to many reported errors for disks
        # which still seem to be OK. The raw value increased by a small amount but the
        # aggregated value remained at it's initial/ok state. So we use the aggregated
        # value now. Only for this field.
        if attribute is DiskAttribute.REALLOCATED_EVENTS:
            try:
                norm_value = disk[f"_normalized_value_{attribute.name}"]
                norm_threshold = disk[f"_normalized_threshold_{attribute.name}"]
            except KeyError:
                yield Result(state=State.OK, summary=infotext)
                yield Metric(attribute.name, value)
                continue
            hints.append("normalized value: %d" % norm_value)
            if norm_value <= norm_threshold:
                state = State.CRIT
                hints[-1] += " (!!)"

        if attribute is DiskAttribute.COMMAND_TIMEOUT_COUNTER:
            rate = get_rate(get_value_store(), "cmd_timeout", time.time(), value)
            state = State.OK if rate < MAX_COMMAND_TIMEOUTS_PER_HOUR / (60 * 60) else State.CRIT
            hints = (
                []
                if state == State.OK
                else [
                    f"counter increased more than {MAX_COMMAND_TIMEOUTS_PER_HOUR} counts / h (!!). "
                    f"Value during discovery was: {ref_value}"
                ]
            )

        yield Result(
            state=state, summary=infotext + " (%s)" % ", ".join(hints) if hints else infotext
        )
        yield Metric(attribute.name, value)


def _display_attribute_name(attribute: DiskAttribute) -> str:
    if (
        lookup_translation := {
            # Can't automatically translate/maintain the upper case abbreviations.
            DiskAttribute.CRC_ERRORS: "CRC errors",
            DiskAttribute.UDMA_CRC_ERRORS: "UDMA CRC errors",
            # "Power_On_Hours" also comes on nvme devices.
            # Since we decided to display "Powered On", we can't translate this automatically.
            DiskAttribute.POWER_ON_HOURS: "Powered on",
        }.get(attribute)
    ) is not None:
        return lookup_translation

    match attribute.name.split("_", maxsplit=1):
        case [first, rest]:
            return f"{first} {rest.lower().replace('_', ' ')}"
        case [only_one]:
            return only_one
        case _:
            # cannot happen
            raise NotImplementedError


register.check_plugin(
    name="smart_stats",
    sections=["smart"],
    service_name="SMART %s Stats",
    discovery_function=discover_smart_stats,
    check_function=check_smart_stats,
    check_default_parameters={},  # needed to pass discovery parameters along!
)
