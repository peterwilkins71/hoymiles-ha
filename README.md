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

## Sensors

| Entity | Source | Refresh |
|---|---|---|
| Solar / Load / Grid / Battery power (W), Solar output of capacity (%) | live "burst" API | 15 s |
| Energy today / this month / this year / total (kWh), Reported power, CO2 avoided | station totals | 5 min |

For the **Energy dashboard**, use *Energy total* as solar production.

## 3. Dashboard card

Install **Power Flow Card Plus** from HACS (Frontend), then add a manual card
(check the entity IDs in Settings → Entities; they follow your station name):

```yaml
type: custom:power-flow-card-plus
title: Solar
entities:
  solar:
    entity: sensor.hoymiles_solar_power
    display_zero_state: true
  home:
    entity: sensor.hoymiles_load_power
  grid:
    entity: sensor.hoymiles_grid_power
watt_threshold: 1000
```

Or with built-in cards only:

```yaml
type: vertical-stack
cards:
  - type: gauge
    entity: sensor.hoymiles_solar_power
    name: Solar now
    min: 0
    max: 800
    needle: true
  - type: entities
    entities:
      - sensor.hoymiles_energy_today
      - sensor.hoymiles_energy_total
  - type: history-graph
    hours_to_show: 24
    entities:
      - sensor.hoymiles_solar_power
```

## Notes

- Without a Hoymiles meter, *Load* just mirrors *Solar* and *Grid*/*Battery* read 0.
- This is an unofficial API; Hoymiles can change it without notice.
