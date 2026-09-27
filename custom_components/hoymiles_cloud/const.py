DOMAIN = "hoymiles_cloud"

CONF_STATION_ID = "station_id"
CONF_STATION_NAME = "station_name"

# The web dashboard polls live data every 3 s; 15 s is plenty for HA and polite to the API.
LIVE_INTERVAL_S = 15
# The cloud only refreshes station totals every 5-15 minutes.
TOTALS_INTERVAL_S = 300
