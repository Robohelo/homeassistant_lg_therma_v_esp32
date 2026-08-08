"""Constants and register definitions for the LG Heatpump (Modbus) integration.

This is a full conversion of your `modbus:` / `template:` YAML
(source comment: "last update: 2026-05-05, for Home Assistant 2026.05").

IMPORTANT - assumptions / corrections made during conversion
==============================================================
Your YAML had a handful of internal inconsistencies. Rather than silently
reproduce something that looks like a copy-paste bug (especially for
registers that get WRITTEN to), each one is flagged below and again at
the relevant definition:

1. `hp_outside_temp` and `hp_water_pressure` both used input register
   address 12 in the original YAML.

   >>> RESOLVED (2026-08, via official register docs - see note 9):
   >>> confirmed `hp_water_pressure` is register 30014 / HA address
   >>> **13**, unit [0.1 bar], not 12. Fixed below - `hp_water_pressure`
   >>> now reads address 13 with scale=0.1/precision=1.
   >>> `hp_outside_temp` correctly stays at address 12. <<<

2. `hp_temp_heatgas`, `hp_high_pressure`, `hp_low_pressure` had no
   `scan_interval` in the YAML. Defaulted to DEFAULT_SCAN_INTERVAL (30s).

3. `hp_compressor_rpm` had `precision: 0.1`, which isn't a valid
   precision (must be an integer digit count). Dropped - no rounding
   applied. `scale: 60` was kept as-is.

   >>> CONTEXT (2026-08, via official docs - see note 9): the raw
   >>> register is documented as "Kompressordrehzahl [Hz]" - so `scale: 60`
   >>> in the original YAML looks like an intentional Hz→RPM approximation
   >>> by whoever wrote it (not an LG-documented conversion factor, and
   >>> not exact for all compressor pole counts) rather than a mistake.
   >>> Left as-is. <<<

4. Template selects `hp_operation_mode_select` and
   `hp_control_method_select` both had `select_option` writing to
   holding register address **9** in your 2026.05 YAML - the same
   address as `hp_energy_state_select`. This was flagged as a likely
   copy/paste error and corrected to write `hp_operation_mode_select`
   to address 0 and `hp_control_method_select` to address 1 (matching
   the holding registers they read their state from).

   >>> CONFIRMED (2026-08 update): your earlier 2024.10 config used a
   >>> different mechanism (`input_select:` + `automation:` writing via
   >>> `modbus.write_register`) for the same two controls, and those
   >>> automations wrote to address 0 (operation mode) and address 1
   >>> (control method) - exactly matching the correction made here.
   >>> No change needed; confidence upgraded from "assumed" to
   >>> "confirmed against your own historical config". <<<
   `hp_energy_state_select` still writes to address 9, which was
   already correct and is unchanged.

   >>> DOUBLY CONFIRMED (2026-08, via official docs - see note 9): the
   >>> LG register documentation lists holding register 40001 (addr 0) as
   >>> "Betriebsmodus" with the exact 0/3/4 = cooling/auto/heating mapping
   >>> used here, register 40002 (addr 1) as "Steuermethode" with the
   >>> exact 0/1/2 mapping used here, and holding register 40010 (addr 9)
   >>> with the exact 9-state "Energiezustand-Eingang" enum used here -
   >>> word for word. All three select write addresses and their option
   >>> mappings are now confirmed against the manufacturer-level docs,
   >>> not just your own historical config. <<<

5. Switches `hp_emergency_stop` (write addr 4) and
   `hp_emergency_stop_switch` (write addr 5) had `verify.address: 2`
   and `verify.address: 3` respectively - the same verify addresses as
   `hp_silent_mode`/`hp_dhw_desinfection_mode`, which also looks
   copy-pasted. This conversion reads back the switch's own write
   address for state instead.

   >>> CONFIRMED for addr 4/5 (2026-08, via official docs - see note 9):
   >>> the register docs list coils 0-5 (hauptschalter, dhw, silent
   >>> mode, disinfection trigger, emergency stop, emergency stop
   >>> trigger) with verify address == write address throughout, matching
   >>> the fix made here.
   >>>
   >>> `hp_active_power_limitation` (write/verify addr 6) is a DIFFERENT
   >>> issue: the official coil register table only documents addresses
   >>> 0-5. There is no address 6 listed at all. This doesn't necessarily
   >>> mean it's wrong (the docs may predate a firmware feature, or your
   >>> unit may differ), but it's now unverified rather than a confirmed
   >>> pattern-match - see note 9. <<<

6. The input-register sensor named `hp_energy_state_input` had
   `unique_id: modbus.hp_energy_state_raw`, and your `hp_energy_state_select`
   template reads `states('sensor.hp_energy_state_raw')` - i.e. the
   entity name and the id used elsewhere didn't match. Keyed as
   `hp_energy_state_raw` here so the select keeps working. This is a
   different register (input reg 11) than `hp_energy_state_input_raw`
   (holding reg 9, "LG WP Energiezustand-Eingang"), which is the
   correct write target and is unchanged.

7. Registers with no explicit `data_type` in the YAML default to
   `int16` here (signed), matching the two's-complement encoding your
   own `number.set_value` templates already used for the shift-value
   registers.

8. (Added 2026-08, after comparing against your 2024.10 config, which
   used `input_number:` + `automation:` instead of `template: number:`)
   The write behaviour of five NUMBER_TYPES entries was CONFIRMED
   against real automations rather than inferred from the 2026.05
   templates alone: `hp_shift_value_in_auto_mode_circuit1_number`
   (address 4, signed two's-complement), `..._circuit2_number`
   (address 7, signed), `hp_hk1_target_temperatur_number` (address 2,
   x10 scale), `hp_hk2_target_temperatur_number` (address 5, x10),
   and `hp_dhw_target_temperatur_number` (address 8, x10) all matched
   exactly. The first four SWITCH_TYPES entries (`hp_hauptschalter`,
   `hp_dhw`, `hp_silent_mode`, `hp_dhw_desinfection_mode`) also matched
   exactly (verify_address == write_address in both configs).

9. (Added 2026-08) Cross-checked the full register map against the
   community-maintained documentation at
   github.com/basti242/homeassistant_lg_therma_v_modbus (wiki page
   "LG Register documentation"). Results:

   CONFIRMED matching exactly: all 17 discrete-input (binary_sensor)
   addresses; coils 0-5 (the first 6 SWITCH_TYPES entries, including
   the emergency-stop verify-address fix from note 5); input registers
   0-6, 8-12, 16, 18-24 (addresses, and the x10/x1 scale pattern);
   holding registers 0-5, 7-9 (addresses and scale pattern); the exact
   option-value mappings and write addresses for all three SELECT_TYPES
   (see note 4).

   NEWLY FIXED based on the wiki (see the entries themselves): `hp_water_pressure`
   address 12→13 plus scale/precision added (note 1); `hp_shift_value_in_auto_mode_circuit1`/
   `..._circuit2` sensor `unit_of_measurement` changed from `°C` to `K`
   to match the documented unit and be consistent with their NUMBER
   counterparts (which already used K).

   ONE WIKI-BASED FIX LATER REVERTED: `hp_product_info` was briefly
   changed to `input_type: holding` here based on the wiki listing
   register 49999 for it - see note 10, an official manual contradicted
   this and it was changed back.

   FLAGGED AS UNVERIFIED AT THE TIME (since resolved or still open -
   see note 10 for the update): `hp_temp_technikraum`, `hp_active_power_limitation`,
   `hp_power_limit`/`hp_power_limit_number`.

   NOT IN YOUR CONFIG AT ALL (documented, but not something this
   integration adds - mentioned here for completeness only): input
   registers 36-45 (paired High/Low 32-bit Wh energy counters), holding
   register 23 "Compressor Modulation", and input registers 39997/39998
   ("Gerätegruppe"/"Geräteinfo", separate from `hp_product_info`).

10. (Added 2026-08) Cross-checked again against the OFFICIAL LG "Therma
    V HM141MR" installer manual (pages 250-253, "Modbus gateway memory
    map"), which you supplied as a PDF. This is a stronger source than
    the community wiki in note 9 - it's the manufacturer's own document
    - but it also only documents a smaller register set (coils 0-5,
    discrete inputs 0-16, "3xxxx" registers 30001-30013 + 39998/39999,
    "4xxxx" registers 40001-40010). Nothing at addresses 30014, 30017-30025,
    30036-30045, holding 23/24, or coil 6 appears anywhere in this
    277-page document - searched the full text, not just pages 250-253.
    That's consistent with the wiki's own footnote that some registers
    "are not available" on products before Dec. 2023; this manual may
    simply predate them. It does NOT contradict `hp_water_pressure`,
    `hp_compressor_rpm`, `hp_temp_liquid_gas`/`..._suction`/`..._heatgas`/
    `..._before_vaporiser`/`..._after_vaporiser`, `hp_high_pressure`,
    `hp_low_pressure`, `hp_active_power_limitation`, or `hp_power_limit`
    - it just doesn't cover that address range either way, so these
    remain exactly as unverified/verified as note 9 left them.

    Two things this manual DOES resolve:

    a) `hp_product_info` - REVERTED (see the entry itself). The manual
       shows register 39999 ("Product Info.", value meanings matching
       exactly: Split/Monobloc/High Temp/Medium Temp/System Boiler) with
       no register 49999 anywhere in the document. 39999 is a "3xxxx"
       register (address 9998 via the same `register - 30001` arithmetic
       used throughout this file), matching the ORIGINAL YAML's
       `input_type: input` exactly. The wiki's "49999" entry for this
       item was very likely the actual error, not your YAML - reverted
       accordingly.

    b) `hp_temp_technikraum` (input addr 7) - CONFIRMED, not just
       flagged. The manual explicitly labels register 30008 (this
       address) "Room air temp. (Circuit 1)" - the same wording used for
       holding addr 3 and input addr 10 (which everyone agrees are
       circuit 1/2 room air temp). This is now confirmed by the
       manufacturer, not just inferred from a pattern. Still NOT renamed
       here (see the entry for why - it's your entity's unique_id/name
       to decide on, and changing it would break existing dashboards/
       automations referencing `sensor.hp_temp_technikraum`), but this
       is as close to certain as this kind of check gets.

    One more thing worth flagging rather than silently acting on: this
    manual's own section headers are inverted relative to standard
    Modbus convention. It labels the "3xxxx" register block (30001-30013,
    39998/39999) as "Holding Register (0x03)" and the "4xxxx" block
    (40001-40010) as "Input Register (0x04)" - backwards from the
    universal Modicon convention (3xxxx=input/function-code-4,
    4xxxx=holding/function-code-3) that this integration, the community
    wiki, and your own original YAML all use consistently. This
    integration was NOT changed to match the manual's literal headers,
    for three reasons: (1) the numeric prefix convention is what
    virtually every Modbus tool/device actually keys off, not prose
    section titles; (2) your own YAML - which you've evidently been
    running - already uses the standard convention throughout, for every
    register, not just this one; (3) flipping every input_type here on
    the strength of two swapped headers, when the alternative explanation
    (a documentation authoring error, plausible for a PDF auto-generated
    from an HTML help page) is at least as likely, risks breaking a
    working integration. If you want to be 100% certain, the fastest
    test is empirical: after installing this integration, check whether
    `sensor.hp_error_code` (address 0) gets a sane value or a Modbus
    exception in the HA logs - if it works, the standard convention
    (and this integration) is correct for your unit.

11. (Added 2026-08) Searched the full 277-page manual for "power limit",
    "limitation", and "modulation" as general terms, not just within the
    memory-map table - zero matches anywhere. The unit does document an
    "energy saving/Smart Grid" feature (physical `TB_SG1`/`TB_SG2` inputs,
    same 8-state enum as `hp_energy_state_select`/holding reg 40010) as
    its demand-response mechanism, which makes a separate "active power
    limitation" register somewhat functionally redundant - weak
    additional evidence against `hp_active_power_limitation`/
    `hp_power_limit` being real on this unit, still not conclusive.
    `kW` appears throughout the manual only as model capacity ratings
    (5/7/9/12/14/16 kW variants), never as a settable limit.

    Also found, unrelated to the register map but relevant to setup
    (see README): enabling Modbus requires a physical DIP switch
    (option switch 1, position 1) on the indoor unit; the native
    interface is RS-485/RTU at connector `CN_COM` (9600-8-N-1), so a
    TCP config in this integration implies an RTU↔TCP gateway sits in
    between; and using Modbus for control disables the LG wall
    controller for the functions controlled that way.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.const import Platform

DOMAIN = "lg_heatpump"
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
]

CONF_SLAVE = "slave"

DEFAULT_PORT = 502
DEFAULT_SLAVE = 1
DEFAULT_SCAN_INTERVAL = 30  # seconds - fallback for entries that had none in the YAML

# Modbus register/input types - same vocabulary as HA's built-in `modbus:` platform.
INPUT_TYPE_INPUT = "input"
INPUT_TYPE_HOLDING = "holding"
INPUT_TYPE_COIL = "coil"
INPUT_TYPE_DISCRETE = "discrete_input"

DATA_TYPE_UINT16 = "uint16"
DATA_TYPE_INT16 = "int16"
DATA_TYPE_UINT32 = "uint32"
DATA_TYPE_INT32 = "int32"
DATA_TYPE_FLOAT32 = "float32"


@dataclass(frozen=True)
class ModbusSensorDescription:
    """Describes a single readable Modbus register (sensor / binary_sensor / switch verify)."""

    key: str
    name: str
    address: int
    input_type: str = INPUT_TYPE_INPUT
    data_type: str = DATA_TYPE_INT16
    count: int = 1
    scale: float = 1
    offset: float = 0
    precision: int | None = None
    unit_of_measurement: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    scan_interval: int = DEFAULT_SCAN_INTERVAL


@dataclass(frozen=True)
class ModbusBinarySensorDescription:
    """Describes a discrete_input register exposed as a binary_sensor."""

    key: str
    name: str
    address: int
    device_class: str | None = None
    scan_interval: int = DEFAULT_SCAN_INTERVAL


@dataclass(frozen=True)
class ModbusSwitchDescription:
    """Describes a writable coil exposed as a switch, with its own read-back address."""

    key: str
    name: str
    write_address: int
    verify_address: int
    scan_interval: int = DEFAULT_SCAN_INTERVAL


@dataclass(frozen=True)
class ModbusSelectDescription:
    """Describes a select entity backed by an existing sensor + a holding-register write."""

    key: str
    name: str
    source_key: str  # key of the ModbusSensorDescription this reads its current value from
    write_address: int
    options: dict[str, int] = field(default_factory=dict)  # label -> raw register value
    default_option: str = ""


@dataclass(frozen=True)
class ModbusNumberDescription:
    """Describes a number entity backed by an existing sensor + a holding-register write."""

    key: str
    name: str
    source_key: str
    write_address: int
    min_value: float
    max_value: float
    step: float
    unit_of_measurement: str | None = None
    write_scale: float = 1  # raw_register_value = round(value * write_scale)
    signed: bool = False  # encode negative values as 16-bit two's complement on write


# ---------------------------------------------------------------------------
# Sensors - Input Registers ("Technische Daten")
# ---------------------------------------------------------------------------
INPUT_SENSOR_TYPES: tuple[ModbusSensorDescription, ...] = (
    ModbusSensorDescription(
        key="hp_error_code", name="Error Code", address=0, scan_interval=10
    ),
    ModbusSensorDescription(
        key="hp_odu_operation_cycle",
        name="ODU Operation Cycle",
        address=1,
        scan_interval=10,
    ),
    ModbusSensorDescription(
        key="hp_inlet_temp",
        name="Inlet Temperature",
        address=2,
        scale=0.1,
        precision=1,
        scan_interval=30,
        unit_of_measurement="°C",
        device_class="temperature",
        state_class="measurement",
    ),
    ModbusSensorDescription(
        key="hp_outlet_temp",
        name="Outlet Temperature",
        address=3,
        scale=0.1,
        precision=1,
        scan_interval=30,
        unit_of_measurement="°C",
        device_class="temperature",
        state_class="measurement",
    ),
    ModbusSensorDescription(
        key="hp_backup_heater_outlet_temp",
        name="Backup Heater Outlet Temperature",
        address=4,  # reg 5
        scale=0.1,
        precision=1,
        scan_interval=30,
        unit_of_measurement="°C",
        device_class="temperature",
        state_class="measurement",
    ),
    ModbusSensorDescription(
        key="hp_dhw_water_temp",
        name="DHW Water Temperature",
        address=5,
        scale=0.1,
        precision=1,
        scan_interval=30,
        unit_of_measurement="°C",
        device_class="temperature",
        state_class="measurement",
    ),
    ModbusSensorDescription(
        key="hp_solar_collector_temp",
        name="Solar Collector Temperature",
        address=6,  # reg 7
        scale=0.1,
        precision=1,
        scan_interval=30,
        unit_of_measurement="°C",
        device_class="temperature",
        state_class="measurement",
    ),
    # CONFIRMED BY THE OFFICIAL LG MANUAL (see note 10), not just the
    # community wiki: register 30008 (this address, 7) is documented as
    # "Room air temp. (Circuit 1)", not a utility-room ("Technikraum")
    # sensor. Kept as originally named since renaming would change this
    # entity's key/unique_id and break any existing dashboards or
    # automations referencing `sensor.hp_temp_technikraum` - but this is
    # about as close to certain as this kind of cross-check gets, so
    # consider renaming both `key` and `name` here once you've confirmed
    # it against your own unit.
    ModbusSensorDescription(
        key="hp_temp_technikraum",
        name="Temperatur Technikraum",
        address=7,
        scale=0.1,
        precision=1,
        scan_interval=10,
        unit_of_measurement="°C",
        device_class="temperature",
        state_class="measurement",
    ),
    ModbusSensorDescription(
        key="hp_flow_rate",
        name="Flow Rate",
        address=8,
        scale=0.1,
        precision=1,
        scan_interval=10,
        unit_of_measurement="l/min",
        device_class="volume_flow_rate",
        state_class="measurement",
    ),
    ModbusSensorDescription(
        key="hp_flow_temp_circle_2",
        name="Flow Temperature Circuit 2",
        address=9,
        scale=0.1,
        precision=1,
        scan_interval=10,
        unit_of_measurement="°C",
        device_class="temperature",
        state_class="measurement",
    ),
    ModbusSensorDescription(
        key="hp_room_air_temp_circuit2_input",
        name="Room Air Temperature Circuit 2 (Input)",
        address=10,
        scale=0.1,
        precision=1,
        scan_interval=10,
        unit_of_measurement="°C",
        device_class="temperature",
        state_class="measurement",
    ),
    # See conversion note 6: keyed to match the original template's
    # `states('sensor.hp_energy_state_raw')` reference.
    ModbusSensorDescription(
        key="hp_energy_state_raw",
        name="Energy State (raw)",
        address=11,
        scan_interval=10,
    ),
    # See conversion note 1: was flagged as colliding with hp_water_pressure -
    # resolved, hp_water_pressure moved to address 13 per official docs.
    ModbusSensorDescription(
        key="hp_outside_temp",
        name="Außentemperatur",
        address=12,
        scale=0.1,
        precision=1,
        scan_interval=10,
        unit_of_measurement="°C",
        device_class="temperature",
        state_class="measurement",
    ),
    # See conversion note 1: address corrected from 12 to 13 per official docs.
    ModbusSensorDescription(
        key="hp_water_pressure",
        name="Water Pressure",
        address=13,  # was 12 in the original YAML - fixed, see note 1 / note 9
        scale=0.1,
        precision=1,
        scan_interval=10,
        unit_of_measurement="Bar",
        device_class="pressure",
        state_class="measurement",
    ),
    ModbusSensorDescription(
        key="hp_temp_liquid_gas",
        name="Temp Liquid Gas",
        address=16,
        scan_interval=10,
        unit_of_measurement="°C",
        device_class="temperature",
        state_class="measurement",
    ),
    ModbusSensorDescription(
        key="hp_temp_suction",
        name="Temperatur Absaugung",
        address=18,
        scan_interval=2,
        unit_of_measurement="°C",
        device_class="temperature",
        state_class="measurement",
    ),
    ModbusSensorDescription(
        key="hp_temp_heatgas",
        name="Heißgastemperatur",
        address=19,
        scan_interval=DEFAULT_SCAN_INTERVAL,  # not set in YAML - see note 2
        unit_of_measurement="°C",
        device_class="temperature",
        state_class="measurement",
    ),
    ModbusSensorDescription(
        key="hp_temp_before_vaporiser",
        name="Dampftemperatur vor Verdampfer",
        address=20,
        scale=0.1,
        precision=1,
        scan_interval=10,
        unit_of_measurement="°C",
        device_class="temperature",
        state_class="measurement",
    ),
    ModbusSensorDescription(
        key="hp_temp_after_vaporiser",
        name="Dampftemperatur nach Verdampfer",
        address=21,
        scale=0.1,
        precision=1,
        scan_interval=10,
        unit_of_measurement="°C",
        device_class="temperature",
        state_class="measurement",
    ),
    ModbusSensorDescription(
        key="hp_high_pressure",
        name="Dampfdruck Kondensator",
        address=22,
        scan_interval=DEFAULT_SCAN_INTERVAL,  # not set in YAML - see note 2
        unit_of_measurement="Bar",
        device_class="pressure",
        state_class="measurement",
    ),
    ModbusSensorDescription(
        key="hp_low_pressure",
        name="Dampfdruck Verdampfer",
        address=23,
        scan_interval=DEFAULT_SCAN_INTERVAL,  # not set in YAML - see note 2
        unit_of_measurement="Bar",
        device_class="pressure",
        state_class="measurement",
    ),
    ModbusSensorDescription(
        key="hp_compressor_rpm",
        name="Kompressordrehzahl",
        address=24,
        scale=60,
        precision=None,  # YAML had an invalid `precision: 0.1` - see note 3
        scan_interval=10,
        unit_of_measurement="U/min",
        state_class="measurement",
    ),
    # RESTORED (see note 10): V2.2 changed this to `input_type: holding`
    # based on the community wiki listing register 49999 for this value.
    # The official LG service manual (Therma V HM141MR, pages 250-253)
    # shows a DIFFERENT register - 39999 - for "Product Info.", with no
    # 49999 entry anywhere in the document. Register 39999 is in the
    # 3xxxx numeric range, i.e. `input`, matching the ORIGINAL YAML
    # exactly. The wiki's "49999" entry for this item now looks like the
    # actual error. Reverted back to the original YAML's `input_type`.
    ModbusSensorDescription(
        key="hp_product_info",
        name="Produktinfos",
        address=9998,
        scan_interval=60,
    ),
)

# ---------------------------------------------------------------------------
# Sensors - Holding Registers
# ---------------------------------------------------------------------------
HOLDING_SENSOR_TYPES: tuple[ModbusSensorDescription, ...] = (
    ModbusSensorDescription(
        key="hp_operation_mode_raw",
        name="Operation Mode (raw)",
        address=0,
        input_type=INPUT_TYPE_HOLDING,
        scan_interval=60,
    ),
    ModbusSensorDescription(
        key="hp_control_method_raw",
        name="Control Method (raw)",
        address=1,
        input_type=INPUT_TYPE_HOLDING,
        scan_interval=60,
    ),
    ModbusSensorDescription(
        key="hp_target_temp_circuit1",
        name="Zieltemperatur HK1",
        address=2,
        input_type=INPUT_TYPE_HOLDING,
        scale=0.1,
        precision=1,
        scan_interval=30,
        unit_of_measurement="°C",
        state_class="measurement",
    ),
    ModbusSensorDescription(
        key="hp_room_air_temp_circuit1",
        name="Room Air Temperature Circuit 1",
        address=3,
        input_type=INPUT_TYPE_HOLDING,
        scale=0.1,
        precision=1,
        scan_interval=30,
        unit_of_measurement="°C",
        device_class="temperature",
        state_class="measurement",
    ),
    # Unit fixed °C -> K per official docs (note 9); matches the K unit
    # already used by the corresponding number entity.
    ModbusSensorDescription(
        key="hp_shift_value_in_auto_mode_circuit1",
        name="Sollwertverschiebung HK1",
        address=4,
        input_type=INPUT_TYPE_HOLDING,
        precision=1,
        scan_interval=30,
        unit_of_measurement="K",
        state_class="measurement",
    ),
    ModbusSensorDescription(
        key="hp_target_temp_circuit2",
        name="Zieltemperatur HK2",
        address=5,
        input_type=INPUT_TYPE_HOLDING,
        scale=0.1,
        precision=1,
        scan_interval=30,
        unit_of_measurement="°C",
        state_class="measurement",
    ),
    ModbusSensorDescription(
        key="hp_room_air_temp_circuit2",
        name="Room Air Temperature Circuit 2",
        address=6,
        input_type=INPUT_TYPE_HOLDING,
        scale=0.1,
        precision=1,
        scan_interval=30,
        unit_of_measurement="°C",
        device_class="temperature",
        state_class="measurement",
    ),
    # Unit fixed °C -> K per official docs (note 9); matches the K unit
    # already used by the corresponding number entity.
    ModbusSensorDescription(
        key="hp_shift_value_in_auto_mode_circuit2",
        name="Sollwertverschiebung HK2",
        address=7,
        input_type=INPUT_TYPE_HOLDING,
        precision=1,
        scan_interval=30,
        unit_of_measurement="K",
        state_class="measurement",
    ),
    ModbusSensorDescription(
        key="hp_dhw_target_temp",
        name="DHW Zieltemperatur",
        address=8,
        input_type=INPUT_TYPE_HOLDING,
        scale=0.1,
        precision=1,
        scan_interval=30,
        unit_of_measurement="°C",
        state_class="measurement",
    ),
    # Write target for energy state (see note 6) - correct, unchanged from YAML.
    ModbusSensorDescription(
        key="hp_energy_state_input_raw",
        name="LG WP Energiezustand-Eingang",
        address=9,
        input_type=INPUT_TYPE_HOLDING,
        scan_interval=10,
    ),
    # UNVERIFIED (see note 9): official docs don't list a holding
    # register at address 24 at all - the table jumps from addr 9
    # straight to addr 23 ("Compressor Modulation": 0, or 40-100 as a
    # percentage - a different concept from a kW power limit) and then
    # addr 9998. May be a newer-firmware register the docs (last edited
    # Feb 2025) don't cover, or may be the wrong address - unconfirmed.
    ModbusSensorDescription(
        key="hp_power_limit",
        name="Power Limit",
        address=24,
        input_type=INPUT_TYPE_HOLDING,
        precision=1,
        scan_interval=10,
        unit_of_measurement="kW",
        device_class="power",
        state_class="measurement",
    ),
)

SENSOR_TYPES: tuple[ModbusSensorDescription, ...] = INPUT_SENSOR_TYPES + HOLDING_SENSOR_TYPES

# ---------------------------------------------------------------------------
# Binary sensors - Discrete Inputs
# ---------------------------------------------------------------------------
BINARY_SENSOR_TYPES: tuple[ModbusBinarySensorDescription, ...] = (
    ModbusBinarySensorDescription(
        key="hp_water_flow_status", name="Water Flow Status", address=0, device_class="problem"
    ),
    ModbusBinarySensorDescription(
        key="hp_water_pump_status", name="Water Pump Status", address=1, device_class="running"
    ),
    ModbusBinarySensorDescription(
        key="hp_ext_water_pump_status",
        name="External Water Pump Status",
        address=2,
        device_class="running",
    ),
    ModbusBinarySensorDescription(
        key="hp_compressor_status", name="Compressor Status", address=3, device_class="running"
    ),
    ModbusBinarySensorDescription(
        key="hp_defrosting_status", name="Defrosting Status", address=4, device_class="running"
    ),
    ModbusBinarySensorDescription(
        key="hp_dhw_heating_status", name="DHW Heating Status", address=5, device_class="running"
    ),
    ModbusBinarySensorDescription(
        key="hp_dhw_tank_desinfection_status",
        name="DHW Tank Desinfection Status",
        address=6,
        device_class="running",
    ),
    ModbusBinarySensorDescription(
        key="hp_silent_mode_status", name="Silent Mode Status", address=7
    ),
    ModbusBinarySensorDescription(
        key="hp_cooling_status", name="Cooling Status", address=8, device_class="running"
    ),
    ModbusBinarySensorDescription(
        key="hp_solar_pump_status", name="Solar Pump Status", address=9, device_class="running"
    ),
    ModbusBinarySensorDescription(
        key="hp_backup_heater_step1_status",
        name="Backup Heater Step 1 Status",
        address=10,
        device_class="running",
    ),
    ModbusBinarySensorDescription(
        key="hp_backup_heater_step2_status",
        name="Backup Heater Step 2 Status",
        address=11,
        device_class="running",
    ),
    ModbusBinarySensorDescription(
        key="hp_dhw_boost_heater_status",
        name="DHW Boost Heater Status",
        address=12,
        device_class="running",
    ),
    ModbusBinarySensorDescription(
        key="hp_error_status", name="Error Status", address=13, device_class="problem"
    ),
    ModbusBinarySensorDescription(
        key="hp_emergency_operation_available_space_heating_cooling",
        name="Emergency Operation Available (Space Heating/Cooling)",
        address=14,
    ),
    ModbusBinarySensorDescription(
        key="hp_emergency_operation_available_dhw",
        name="Emergency Operation Available (DHW)",
        address=15,
    ),
    ModbusBinarySensorDescription(
        key="hp_mix_pump_status", name="Mix Pump Status", address=16, device_class="running"
    ),
)

# ---------------------------------------------------------------------------
# Switches - Coils (see notes 5 for verify_address corrections)
# ---------------------------------------------------------------------------
SWITCH_TYPES: tuple[ModbusSwitchDescription, ...] = (
    ModbusSwitchDescription(
        key="hp_hauptschalter", name="Wärmepumpe Hauptschalter", write_address=0, verify_address=0
    ),
    ModbusSwitchDescription(
        key="hp_dhw", name="Warmwasserbereitung", write_address=1, verify_address=1
    ),
    ModbusSwitchDescription(
        key="hp_silent_mode", name="LG WP Ruhemodus", write_address=2, verify_address=2
    ),
    ModbusSwitchDescription(
        key="hp_dhw_desinfection_mode",
        name="DHW Desinfektionsmodus",
        write_address=3,
        verify_address=3,
    ),
    ModbusSwitchDescription(
        key="hp_emergency_stop",
        name="Emergency Stop",
        write_address=4,
        verify_address=4,  # YAML had verify_address 2 - see note 5, CONFIRMED per official docs
    ),
    ModbusSwitchDescription(
        key="hp_emergency_stop_switch",
        name="Emergency Stop Switch",
        write_address=5,
        verify_address=5,  # YAML had verify_address 3 - see note 5, CONFIRMED per official docs
    ),
    # UNVERIFIED (see note 5/9): official coil register docs only list
    # addresses 0-5. Address 6 isn't documented at all - may be a
    # newer-firmware coil, or may not exist on your unit.
    ModbusSwitchDescription(
        key="hp_active_power_limitation",
        name="Active Power Limitation",
        write_address=6,
        verify_address=6,
    ),
)

# ---------------------------------------------------------------------------
# Selects (template selects converted to native select entities)
# ---------------------------------------------------------------------------
SELECT_TYPES: tuple[ModbusSelectDescription, ...] = (
    ModbusSelectDescription(
        key="hp_operation_mode_select",
        name="Operation Mode",
        source_key="hp_operation_mode_raw",
        write_address=0,  # YAML wrote to address 9 - see note 4. CONFIRMED
                          # per official docs (holding reg 40001).
        options={"Cooling": 0, "Auto": 3, "Heating": 4},
        default_option="Auto",
    ),
    ModbusSelectDescription(
        key="hp_control_method_select",
        name="Control Method",
        source_key="hp_control_method_raw",
        write_address=1,  # YAML wrote to address 9 - see note 4. CONFIRMED
                          # per official docs (holding reg 40002).
        options={
            "Water Outlet Temperature Control": 0,
            "Water Inlet Temperature Control": 1,
            "Room Air Control": 2,
        },
        default_option="Water Outlet Temperature Control",
    ),
    ModbusSelectDescription(
        key="hp_energy_state_select",
        name="Energy State",
        source_key="hp_energy_state_raw",
        write_address=9,  # correct in the original YAML. CONFIRMED per
                          # official docs (holding reg 40010) - see note 4.
        options={
            "Not used": 0,
            "Forced Off": 1,
            "Normal Operation": 2,
            "On - Recommendation": 3,
            "On - Command": 4,
            "On - Command Step 2": 5,
            "On - Recommendation Step 1": 6,
            "Power Saving Mode": 7,
            "Super Power Saving Mode": 8,
        },
        default_option="Not used",
    ),
)

# ---------------------------------------------------------------------------
# Numbers (template numbers converted to native number entities)
# ---------------------------------------------------------------------------
NUMBER_TYPES: tuple[ModbusNumberDescription, ...] = (
    ModbusNumberDescription(
        key="hp_shift_value_in_auto_mode_circuit1_number",
        name="Sollwertverschiebung HK1",
        source_key="hp_shift_value_in_auto_mode_circuit1",
        write_address=4,
        min_value=-5,
        max_value=5,
        step=1,
        unit_of_measurement="K",
        write_scale=1,
        signed=True,
    ),
    ModbusNumberDescription(
        key="hp_shift_value_in_auto_mode_circuit2_number",
        name="Sollwertverschiebung HK2",
        source_key="hp_shift_value_in_auto_mode_circuit2",
        write_address=7,
        min_value=-5,
        max_value=5,
        step=1,
        unit_of_measurement="K",
        write_scale=1,
        signed=True,
    ),
    ModbusNumberDescription(
        key="hp_hk1_target_temperatur_number",
        name="HK1 Solltemperatur",
        source_key="hp_target_temp_circuit1",
        write_address=2,
        min_value=30,
        max_value=50,
        step=1,
        unit_of_measurement="°C",
        write_scale=10,
    ),
    ModbusNumberDescription(
        key="hp_hk2_target_temperatur_number",
        name="HK2 Solltemperatur",
        source_key="hp_target_temp_circuit2",
        write_address=5,
        min_value=20,
        max_value=40,
        step=1,
        unit_of_measurement="°C",
        write_scale=10,
    ),
    ModbusNumberDescription(
        key="hp_dhw_target_temperatur_number",
        name="DHW Solltemperatur",
        source_key="hp_dhw_target_temp",
        write_address=8,
        min_value=45,
        max_value=60,
        step=1,
        unit_of_measurement="°C",
        write_scale=10,
    ),
    ModbusNumberDescription(
        key="hp_room_air_temp_circuit1_number",
        name="Raumlufttemperatur HK1",
        source_key="hp_room_air_temp_circuit1",
        write_address=3,
        min_value=10,
        max_value=35,
        step=0.1,
        unit_of_measurement="°C",
        write_scale=10,
    ),
    ModbusNumberDescription(
        key="hp_room_air_temp_circuit2_number",
        name="Raumlufttemperatur HK2",
        source_key="hp_room_air_temp_circuit2",
        write_address=6,
        min_value=10,
        max_value=35,
        step=0.1,
        unit_of_measurement="°C",
        write_scale=10,
    ),
    ModbusNumberDescription(
        key="hp_power_limit_number",
        name="Leistungsbegrenzungswert",
        source_key="hp_power_limit",
        write_address=24,
        min_value=0.1,
        max_value=25.0,
        step=0.1,
        unit_of_measurement="kW",
        write_scale=1,
    ),
)
