# LG Heatpump (Modbus) — Home Assistant Integration

**V2.5** — full conversion of your entire `modbus:` + `template:` YAML
(23 input registers, 11 holding registers, 17 discrete inputs, 7 coils, 3
template selects, 8 template numbers) into a HACS-installable integration
with a UI config flow, five entity platforms, and no more `secrets.yaml`
editing.

## What you get

| Platform | Count | Source in your YAML |
|---|---|---|
| `sensor` | 34 | `modbus.sensors` (input + holding registers) |
| `binary_sensor` | 17 | `modbus.binary_sensors` (discrete_input) |
| `switch` | 7 | `modbus.switches` (coil) |
| `select` | 3 | `template.select` |
| `number` | 8 | `template.number` |

All entities are grouped under a single device, and registers that share a
`scan_interval` are polled together by one coordinator (fewer, more
efficient Modbus requests than one poller per sensor).

## Installation

### Via HACS
1. HACS → "⋮" menu → **Custom repositories** → add this repo, category
   **Integration**.
2. Install "LG Heatpump (Modbus)", restart Home Assistant.

### Manual
Copy `custom_components/lg_heatpump/` into `config/custom_components/`,
restart Home Assistant.

## Setup

Settings → Devices & Services → **Add Integration** → "LG Heatpump
(Modbus)" → enter:

| Field | Replaces |
|---|---|
| Host | `lg_heatpump_modbus_host_ip` secret |
| Port | `lg_heatpump_modbus_port` secret |
| Slave / Unit ID | `lg_heatpump_modbus_slave` secret |

`timeout`/`retries` from your hub config aren't currently exposed in the
config flow (pymodbus's `AsyncModbusTcpClient` uses its own defaults) — see
"Possible follow-ups" below if you want those configurable.

### 🔌 Before the config flow will connect to anything

Found while reading the rest of your official manual (not in the Modbus
memory-map pages, but relevant if you're setting this up from scratch):

- **A physical DIP switch must be enabled on the indoor unit first.**
  Page 249: *"Modbus Address... To use this function, switch No.1 of
  option switch 1 must be turned ON."* If that switch is off, the unit
  won't respond on Modbus at all, regardless of anything in this
  integration or your YAML - worth checking first if you're getting
  connection timeouts.
- **The heat pump's native Modbus interface is RS-485 (RTU), not TCP.**
  It's exposed on the indoor PCB at connector `CN_COM` (terminals
  A/B), 9600 baud / 1 stop bit / no parity. Your config (both the
  2024.10 and 2026.05 YAML, and `type: tcp` in this integration) talks
  Modbus **TCP** to a `host`/`port`, which means you're going through an
  RTU↔TCP gateway device sitting between Home Assistant and those A/B
  terminals - if you ever need to reconfigure that gateway (not this
  integration), those are the serial parameters it needs on its RTU side.
- **Enabling 3rd-party (Modbus) control disables the LG wall controller
  for the functions you control this way.** Page 81: *"If 3rd party
  controller is used, LG controller is not applied to AWHP
  simultaneously."* Not a bug in this integration - just worth knowing
  before you flip switches expecting the wall panel to keep working
  exactly as before.

## ⚠️ Things I changed vs. your literal YAML — status after cross-checking

Your 2026.05 config had a few internal inconsistencies. Rather than
silently reproduce anything that *writes* to the heat pump if it looked
like a copy/paste bug, each one was flagged, then checked against three
increasingly authoritative sources as they became available: your older
2024.10 config (real `automation:` blocks instead of templates), a
community wiki register map, and finally the **official LG "Therma V
HM141MR" installer manual** you provided as a PDF. Status below reflects
all three; everything is also documented inline in `const.py`.

### ✅ Confirmed (by your 2024.10 automations, the wiki, and/or the official manual)

- **`hp_operation_mode_select`** → holding reg **0**, **`hp_control_method_select`**
  → holding reg **1** (not 9, as the 2026.05 YAML literally had it).
  Matches your 2024.10 automations AND the official manual's holding
  registers 40001/40002 word-for-word, including the exact option-value
  mappings.
- **`hp_energy_state_select`** → holding reg **9**. Matches the official
  manual's holding register 40010 exactly, including all 9 option labels
  and values - upgraded from "plausible" to fully confirmed.
- **Numbers** `hp_shift_value_in_auto_mode_circuit1_number`/`..._circuit2_number`
  (signed two's-complement), `hp_hk1_target_temperatur_number`,
  `hp_hk2_target_temperatur_number`, `hp_dhw_target_temperatur_number`
  (×10 scale) - matched 2024.10 automations exactly.
- **Switches** `hp_hauptschalter`, `hp_dhw`, `hp_silent_mode`,
  `hp_dhw_desinfection_mode`, `hp_emergency_stop`, `hp_emergency_stop_switch`
  (coils 0-5) - verify address == write address, matching the official
  manual's coil table exactly (all 6 entries, word-for-word descriptions).
- **All 17 binary_sensor addresses** and their descriptions match the
  official manual's discrete-input table exactly.
- **`hp_temp_technikraum`** (input addr 7) is now **confirmed mislabelled**
  by the official manual itself: register 30008 is documented as "Room
  air temp. (Circuit 1)", not a utility-room sensor. Left as originally
  named (renaming would change the entity's unique_id and break existing
  dashboards/automations) - but if you're setting this up fresh, consider
  renaming it.

### ↩️ Fixed, then reverted (wiki vs. official manual disagreed)

- **`hp_product_info`**: briefly changed to `input_type: holding` based
  on the community wiki listing register 49999 for it. The official
  manual shows a different register - **39999** - for "Product Info.",
  with no 49999 anywhere in the document. 39999 is an input-type
  register, matching your **original YAML exactly**. Reverted back -
  the wiki's entry for this one item looks like the actual error.

### ⚠️ Still unverified (not in the official manual at all)

This manual only documents a base register set - it doesn't cover
addresses 30014, 30017-30025, energy meters, holding 23/24, or coil 6 at
all (searched all 277 pages, not just the memory-map pages), which lines
up with the wiki's own note that some registers aren't available on
units from before Dec. 2023. That means these remain exactly as
verified/unverified as before - not contradicted, just not covered:

- **`hp_water_pressure`** (addr 13, fixed from the wiki - see below)
- **`hp_active_power_limitation`** (coil addr 6) - no coil above address
  5 is documented anywhere, by either source. Also searched the full
  manual for "power limit", "limitation", and "modulation" as general
  terms (not just in the memory-map table) - zero matches anywhere in
  277 pages. The unit *does* document an "energy saving/Smart Grid"
  feature (physical `TB_SG1`/`TB_SG2` inputs, same 8-state enum as
  `hp_energy_state_select`) as its demand-response mechanism, which
  makes a separate "active power limitation" coil somewhat redundant
  functionally - slightly weaker odds this register is real on your
  unit, but still not proof either way.
- **`hp_power_limit`/`hp_power_limit_number`** (holding addr 24) - same
  search, same result: no mention anywhere. The manual's `kW` mentions
  are all model capacity ratings (5/7/9/12/14/16 kW variants), never a
  settable power-limit feature.
- `hp_temp_liquid_gas`, `hp_temp_suction`, `hp_temp_heatgas`,
  `hp_temp_before_vaporiser`, `hp_temp_after_vaporiser`, `hp_high_pressure`,
  `hp_low_pressure`, `hp_compressor_rpm` (addr 16-24) - addresses only
  confirmed against the wiki, not the official manual. Worth noting:
  the manual's wiring diagrams do independently confirm a physical
  "water pressure sensor" (`CN_H2O_PRESS`) and compressor
  discharge/suction temperature sensors exist on the unit - so the
  *hardware* is there, it's specifically the *Modbus register addresses*
  for them that this manual doesn't document.

### 🔎 Resolved via the wiki, unconfirmed by the official manual

- **`hp_water_pressure`**: address fixed from 12 to **13**, with
  scale=0.1/precision=1 added - confirmed by the wiki (register 30014,
  "[0.1 bar ×10]"), consistent with your 2024.10 config never having this
  sensor and address 13 being otherwise unused. Not covered by the
  official manual excerpt either way.
- **`hp_shift_value_in_auto_mode_circuit1`/`..._circuit2`** sensor unit
  changed from `°C` to `K`, matching both the wiki and the official
  manual's "1K" unit, and the NUMBER entities which already used K.

### 📄 A note on the official manual's own labelling

The official manual's Modbus memory map (pages 250-253) labels the
30001-30013/39998/39999 register block "**Holding** Register (0x03)"
and the 40001-40010 block "**Input** Register (0x04)" - backwards from
the standard Modbus numbering convention (3xxxx=input, 4xxxx=holding)
that this integration, the community wiki, and your own 2024.10/2026.05
YAML all use consistently. This wasn't changed to match the manual's
literal headers: the numeric-prefix convention is what Modbus tooling
actually keys off, your own YAML already uses it consistently for every
register (not just isolated ones), and flipping every `input_type` on
the strength of two swapped section titles risks breaking a
presumably-working integration on the strength of what looks like a
documentation/PDF-generation error. If you want certainty, the fastest
check is empirical: watch the HA logs after setup - if `sensor.hp_error_code`
gets a real value instead of a Modbus exception, the standard convention
(and this integration) is correct for your unit.

### Unrelated to the above

- **`hp_temp_heatgas`, `hp_high_pressure`, `hp_low_pressure`** have no
  `scan_interval` in any source config — defaulted to 30s.
- **`hp_compressor_rpm`**'s invalid `precision: 0.1` has existed since at
  least 2024.10 — dropped, sensor is unrounded. The official manual
  confirms the raw register is in **Hz**, so `scale: 60` looks like an
  intentional (if approximate) Hz→RPM conversion by whoever wrote the
  original YAML, not a mistake — kept as-is.

## What changed between your 2024.10 and 2026.05 configs

For reference, here's what actually differs between the two YAML versions
you've shared (useful context for the confirmations/gaps above):

**Added in 2026.05:**
- Hub-level `timeout: 5`, `retries: 3`
- `hp_flow_rate` gained `device_class: volume_flow_rate`
- New holding sensor `hp_power_limit` (addr 24)
- New switches: `hp_emergency_stop` (4), `hp_emergency_stop_switch` (5),
  `hp_active_power_limitation` (6)
- `device_class` added to most binary_sensors (previously none had one)
- New numbers: room air temp circuit 1/2, power limit
- The whole `template: select:` block (3 selects), replacing...

**Removed in 2026.05 (present in 2024.10):**
- `input_select:` (2 entries) + `input_number:` (5 entries)
- ~10 `automation:` entries bridging those to Modbus registers
- 9 individual per-state `template: binary_sensor:` entries for energy
  state, replaced by the single `hp_energy_state_select` dropdown

**Renamed only (same register/address, cosmetic):**
- `hp_operation_mode` → `hp_operation_mode_raw`,
  `hp_control_method` → `hp_control_method_raw` (unique_id also changed —
  irrelevant to this integration since it generates its own unique_ids)
- `hp_silent_mode` → display name "LG WP Ruhemodus" (unique_id unchanged)
- `hp_energy_state_input_raw` → display name "LG WP Energiezustand-Eingang"
  (unique_id unchanged)

**Unchanged:** every input/holding register address that exists in both
versions, and all binary_sensor addresses.

## Adding or changing registers

Everything lives in `const.py`, grouped into five tuples:
`INPUT_SENSOR_TYPES` / `HOLDING_SENSOR_TYPES` (merged into `SENSOR_TYPES`),
`BINARY_SENSOR_TYPES`, `SWITCH_TYPES`, `SELECT_TYPES`, `NUMBER_TYPES`. Add,
remove, or edit an entry there and restart — no other file needs to
change.

## Notes / possible follow-ups

- **pymodbus compatibility is now handled at runtime**, not by pinning a
  narrow version range — see "Fixed: install crash" below for why and
  how. `manifest.json` now requires `pymodbus>=3.6.9,<4.0.0`, wide enough
  to avoid conflicting with whatever version HA's own dependency
  resolver settles on across HA versions.
- `timeout`/`retries` from your hub-level YAML aren't wired into the
  config flow yet — easy to add as extra optional fields in
  `config_flow.py` and pass to `AsyncModbusTcpClient(..., timeout=..., retries=...)`
  if you want them configurable from the UI.
- Register definitions (including the write addresses used by
  select/number/switch entities) live in code, not the UI. Turning that
  into an options-flow-editable list is a reasonable next step if you
  want to change registers without editing Python.
- Update `manifest.json`'s `codeowners`/`documentation`/`issue_tracker`
  to your own GitHub username/repo before publishing.

## 🔧 Fixed: install crash (`RequirementsNotFound`)

If you hit this on setup:

```
homeassistant.requirements.RequirementsNotFound: Requirements for lg_heatpump not found: ['pymodbus>=3.6.0,<3.9.0'].
```

That was `manifest.json` pinning a pymodbus range that no longer matches
reality. Home Assistant runs every integration in one shared Python
environment, so this integration doesn't get its own isolated pymodbus -
it gets whatever version HA's dependency resolver already settled on
(usually driven by HA core's own built-in `modbus` integration, which has
moved to newer pymodbus releases - 3.10+, sometimes much newer - faster
than a `<3.9.0` upper bound could keep up with). When two loaded
integrations require mutually-exclusive version ranges, `pip`'s resolver
can't satisfy both and setup fails outright, before any of this
integration's own code even runs.

Two things changed to fix this:

1. **`manifest.json`** now requires `pymodbus>=3.6.9,<4.0.0` - wide
   enough to not fight with HA core's own pin on any currently-supported
   HA version.
2. **Every `slave=` keyword argument was replaced with a runtime check**
   (new `modbus_compat.py`). pymodbus 3.10.0 renamed `slave=` to
   `device_id=` and dropped the old name entirely rather than keeping it
   as a deprecated alias, so simply widening the version range wasn't
   enough on its own - code built against the old kwarg would still
   crash on the newer pymodbus that range now allows in. `count` (and
   other read/write parameters) also became keyword-only around
   pymodbus 3.8.0, so every Modbus call in this integration was changed
   to pass all its arguments as keywords, not just the device-id one.

This was tested against the actual pymodbus 3.14.0 API (current as of
Aug 2026) - `modbus_compat.get_pymodbus_device_param()` correctly
resolves to `device_id`, and every read/write call's arguments were
checked to bind against pymodbus 3.14.0's real method signatures.
Credit for this exact pattern goes to a Home Assistant community
writeup on the same problem in a different Modbus integration:
https://community.home-assistant.io/t/managing-pymodbus-versions-in-custom-integrations/823773

## Version history

- **V2.5** — fixed an install-crash bug (`RequirementsNotFound`): the
  `pymodbus>=3.6.0,<3.9.0` pin in `manifest.json` conflicted with the
  newer pymodbus HA's own dependency resolver installs. Widened the pin
  to `pymodbus>=3.6.9,<4.0.0` and added a runtime compatibility shim
  (`modbus_compat.py`) so every Modbus read/write call uses `device_id=`
  on pymodbus ≥3.10.0 and `slave=` on older versions, since the range
  widening alone would have let in a pymodbus version whose renamed
  kwarg the old code didn't know about. Verified against the real
  pymodbus 3.14.0 API, not just reasoned about.
- **V2.4** — no address/logic changes. Searched the full manual (not just
  the memory-map pages) for "power limit"/"modulation"/"limitation" -
  found nothing, adding weak additional evidence against
  `hp_active_power_limitation`/`hp_power_limit` (documented in README/
  const.py, not acted on). Added a "before you start" section covering
  three practical setup facts pulled from the manual: the required DIP
  switch, the RS-485/RTU↔TCP gateway implication, and that Modbus
  control disables the LG wall controller for those functions.
- **V2.3** — cross-checked the register map against the official LG
  "Therma V HM141MR" installer manual (PDF you provided). Reverted
  `hp_product_info`'s V2.2 `input_type` change back to the original
  (the manual contradicts the wiki here and matches your original YAML).
  Upgraded `hp_temp_technikraum`'s mislabel flag from "community wiki
  suggests" to "official manual confirms". Documented a header
  inconsistency in the manual itself (see README) without acting on it.
- **V2.2** — cross-checked the register map against a community wiki
  (github.com/basti242/homeassistant_lg_therma_v_modbus). Fixed
  `hp_water_pressure` address (12→13) and added scale/precision; fixed
  `hp_product_info`'s input_type (later reverted in V2.3); fixed
  `hp_shift_value_in_auto_mode_circuit1`/`..._circuit2` sensor units
  (°C→K). Flagged `hp_temp_technikraum`, `hp_active_power_limitation`,
  `hp_power_limit` as unverified against this source.
- **V2.1** — no functional/address changes. Cross-checked V2.0's flagged
  assumptions against a 2024.10 version of this config (which used
  `automation:` blocks instead of templates) and updated documentation
  in `const.py`/README to mark which corrections are now confirmed vs.
  still best-effort guesses. Strengthened the `hp_water_pressure`
  address-collision note.
- **V2.0** — full conversion: added binary_sensor, switch, select, and
  number platforms for the complete register map (was previously just
  one example sensor in V1.0).
- **V1.0** — initial conversion from YAML (single `hp_error_code` sensor,
  config flow, coordinator scaffolding).
