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
  carry no device class. **Outdoor temperature fed** (diagnostic) says
  whether the boiler is using a fed outdoor temperature.

## Feeding the outdoor temperature (option)

If the boiler's own outdoor sensor reads wrong, for example because it sits in
sun, its outdoor reset and warm-weather shutdown follow the wrong number.
Under the integration's **Configure** options, pick any Home Assistant
temperature sensor as the **Outdoor temperature source**. The integration then
writes that sensor's value into the boiler every 30 seconds in place of its
outdoor sensor.

- The boiler needs ModBus/BACnet set to **ACTIVE** in its installer menu
  (Control Modes).
- It fails safe. If the source has no usable value, the integration hands the
  outdoor temperature back to the boiler's sensor at once. If Home Assistant
  or the link stops, the boiler keeps the last value for about 5 minutes
  (measured: 5 min 10 s), then goes back to its own sensor. Its 10 s ModBus
  timeout doesn't apply to the outdoor value.
- While fed, the **Outdoor temperature** sensor shows the fed value. The
  board has no other register for its own sensor.
- In Fahrenheit, values under 32 °F are written as 32 °F. Tested on a live
  boiler: it reads a fed value below freezing as hot and goes into
  warm-weather shutdown (its own sensor is fine below freezing). A reset
  curve is at its cap long before 32 °F, so the clamp changes nothing.
- Clear the option to stop feeding.

### Fahrenheit boilers only, for now

Everything above was worked out and tested on a boiler whose display is set
to **Fahrenheit**:

- the 32 °F floor;
- why a fed value below freezing trips warm-weather shutdown;
- the ~5 minute fallback;
- the 0.1 °F units.

A Fahrenheit boiler converts each value we write from °F to °C itself, and
that conversion breaks below freezing (details in the
[lochinvar-modbus README](https://github.com/cwm12345/lochinvar-modbus#writes-the-outdoor-temperature-only)).

A boiler set to **Celsius** would work differently. Per the manual, it takes
signed tenths of a degree C with no conversion. So the freezing limit, and
whether below-freezing values work at all, would likely differ.

**The integration doesn't handle the Celsius case at this time.** It has a
Celsius code path (values clamped to -40 to 60 °C), but that path has never
been run against a Celsius boiler. Don't rely on the feed with one until it
has been tested.

## Up front

This was built for one installation and is shared as a starting point. I'm
not planning to be a long-term maintainer; fork freely.

## License

[Unlicense](LICENSE): public domain.
