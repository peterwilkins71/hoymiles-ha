# Hoymiles S-Miles Cloud for Home Assistant

Cloud-polling integration for Hoymiles inverters whose firmware no longer exposes
the local DTU port (10081). Reverse engineered from the global.hoymiles.com web app.

## 1. Check your login works (optional, 1 minute)

```bash
uv run tools/probe.py you@example.com
```

Prompts for the password, then prints one set of totals and one live reading.

## 2. Install

Copy `custom_components/hoymiles_cloud` into your HA config's `custom_components/`
(e.g. via the Samba or File editor add-on), restart HA, then
**Settings → Devices & services → Add integration → Hoymiles S-Miles Cloud**.

The password is stored in the config entry (same as any cloud integration) and is
used to log in again automatically when the token expires.

## Entities

| Entity | Source | Refresh |
|---|---|---|
| Solar power (W), Solar output of capacity (%) | live "burst" API | 5 s |
| Producing (on/off) | live "burst" API | 5 s |
| Energy today / this month / this year / total (kWh), Reported power, CO2 avoided | station totals | 5 min |

Load, grid and battery power are not provided: without a Hoymiles meter the API
copies solar into load and reports grid and battery as 0. Upgrading from 0.1.0
removes those entities automatically.

For the **Energy dashboard**, use *Energy total* as solar production.

## Dashboard card

Built-in cards only. The tile turns green while producing and grey otherwise
(check the entity IDs in Settings → Entities; they follow your station name):

```yaml
type: vertical-stack
cards:
  - type: tile
    entity: sensor.hoymiles_solar_power
    name: Solar now
    color: green
    visibility:
      - condition: state
        entity: binary_sensor.hoymiles_producing
        state: "on"
  - type: tile
    entity: sensor.hoymiles_solar_power
    name: Solar now
    color: disabled
    visibility:
      - condition: state
        entity: binary_sensor.hoymiles_producing
        state: "off"
  - type: entities
    entities:
      - sensor.hoymiles_energy_today
      - sensor.hoymiles_energy_total
  - type: history-graph
    hours_to_show: 24
    entities:
      - sensor.hoymiles_solar_power
```

With Mushroom (HACS) a single card does it:

```yaml
type: custom:mushroom-template-card
entity: sensor.hoymiles_solar_power
primary: Solar now
secondary: "{{ states(entity) }} W"
icon: mdi:solar-power
icon_color: "{{ 'green' if is_state('binary_sensor.hoymiles_producing', 'on') else 'grey' }}"
```

## Notes

- Without a Hoymiles meter, *Load* just mirrors *Solar* and *Grid*/*Battery* read 0.
- This is an unofficial API; Hoymiles can change it without notice.
