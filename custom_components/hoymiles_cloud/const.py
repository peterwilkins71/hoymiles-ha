DOMAIN = "hoymiles_cloud"

CONF_STATION_ID = "station_id"
CONF_STATION_NAME = "station_name"

# The web dashboard polls live data every 3 s, but the inverter only uploads a new
# reading every ~5-10 s, so polling faster than 5 s just repeats the last value.
LIVE_INTERVAL_S = 5
# The cloud only refreshes station totals every 5-15 minutes.
TOTALS_INTERVAL_S = 300

# Above this the station counts as producing (avoids flicker from standby trickle at dusk).
PRODUCING_THRESHOLD_W = 1.0
