"""Tests for the Lochinvar boiler integration."""

# Written by Claude, guided by Chris.

from modbus_connection.mock import MockModbusUnit

from homeassistant.const import CONF_HOST, CONF_PORT

MOCK_HOST = "192.0.2.10"
MOCK_USER_INPUT = {
    CONF_HOST: MOCK_HOST,
    CONF_PORT: 502,
    "unit_id": 1,
    "temperature_unit": "°F",
}
MOCK_UNIQUE_ID = f"{MOCK_HOST}:502:1"

# A real Knight Wall Hung boiler, display in Fahrenheit, read live while idle
# with its boiler pump running out a pump delay. Zero-based addresses.
INPUT: dict[int, int] = {
    0: 62,  # inputs 1-16: flow, gas pressure, louver proving, APS, drain
    1: 0,
    2: 4,  # inputs 33-48: CH pump
    3: 32,  # system setpoint: none
    4: 0,  # system pump speed
    5: 0,  # cascade total power: not in a cascade
    6: 0,
    7: 32,  # outlet setpoint: none
    8: 986,  # outlet 98.6 F
    9: 971,  # inlet 97.1 F
    10: 843,  # flue 84.3 F
    11: 0,  # firing rate
    12: 9,  # boiler pump speed 9 %
    13: 33,  # status: heating pump delay
    14: 0,  # blocking: none
    15: 32767,  # lockout: code not present
}
HOLDING: dict[int, int] = {
    0: 0,  # BMS configuration
    1: 0,  # BMS command
    2: 0,  # rate command
    3: 124,  # tank setpoint 124 F
    4: 1196,  # tank 119.6 F
    5: 629,  # outdoor 62.9 F
    6: 9321,  # system supply: no sensor
    7: 9321,  # DHW recirculation: no sensor
}


def seed_boiler(unit: MockModbusUnit) -> None:
    """Seed a mock unit as the live boiler."""
    for address, value in INPUT.items():
        unit.input[address] = value
    for address, value in HOLDING.items():
        unit.holding[address] = value
