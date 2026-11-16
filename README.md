<!-- Written by Claude, guided by Chris. -->

# Lochinvar boilers for Home Assistant

A Home Assistant integration for Lochinvar boilers and water heaters with the
MODB-I-O Modbus communication board (Knight, Knight XL, Armor, Wall Hung, Wall
Mount, FTXL, AQUAS, Shield and their outdoor versions), reached through a
Modbus TCP gateway. Read-only.

It follows Home Assistant's Modbus integration pattern: the device model lives
in the [lochinvar-modbus](https://github.com/cwm12345/lochinvar-modbus)
library, the integration is written in core's layout under `core/`, and
`scripts/vendor.py` builds the HACS version in `custom_components/` with the
library vendored in.

Requires Home Assistant 2026.10 or newer (the `modbus` integration's shared
connections and modbus-connection 4.12+).

## Installation

**With HACS** (recommended, so you're told about updates):

1. In Home Assistant, open **HACS**, then the **⋮** menu (top right) →
   **Custom repositories**.
2. Repository: `https://github.com/cwm12345/ha-lochinvar`, type:
   **Integration**. Click **Add**.
3. Search HACS for **Lochinvar**, open it and click **Download**.
4. Restart Home Assistant.

**Manually:** copy the `custom_components/lochinvar` folder from this
repository into your Home Assistant `config/custom_components/` folder (create
`custom_components` if it doesn't exist), then restart Home Assistant.

You don't need to install the `lochinvar-modbus` library separately; a copy is
included in `custom_components/lochinvar`.

## Setup

Settings → Devices & services → Add integration → Lochinvar, then give:

- the gateway's host and TCP port;
- the board's Modbus unit ID (DIP switches 1-8, default 1);
- the **temperature unit the boiler's display is set to**. The boiler sends
  temperatures in its display unit, not always the Celsius the manual
  documents; see the library's README.

## Entities

- **Sensors:** outlet, inlet, flue, tank and outdoor temperatures; outlet and
  tank setpoints; firing rate; boiler and system pump speeds; status, blocking
  and lockout reason (decoded), plus the raw codes and BMS registers as
  diagnostics. System supply, system setpoint and DHW recirculation appear
  only when those sensors are connected; cascade power only when the boiler
  is in a cascade.
- **Binary sensors:** flame, gas valve, the pumps, thermostat demands, the
  safety switches, alarm and run-time contacts, and a lockout problem
  sensor. The manual only gives each input as ON/OFF, so the safety switches
  carry no device class.

## Up front

This was built for one installation and is shared as a starting point. I'm
not planning to be a long-term maintainer; fork freely.

## License

[Unlicense](LICENSE): public domain.
