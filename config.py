from datetime import time

# Timezone configuration - IANA name
LOCAL_TIMEZONE = "America/Los_Angeles"  # change to your desired timezone

# Configuration for presence detection
PHONE_IPS = {
    "Tim": "192.168.0.157",
    "Koi": "192.168.0.110",
}

# Daytime window (interpreted in LOCAL_TIMEZONE)
DAYTIME_START = time(6, 0)
DAYTIME_END = time(20, 0)

# Continuous monitoring configuration
CHECK_INTERVAL_SECONDS = 30  # How often main loop checks conditions
MAX_API_CALLS_PER_DAY = 20

# Night check times (hours in 24-hour format, in LOCAL_TIMEZONE)
NIGHT_CHECK_HOURS = [20, 22, 0, 4]

# Presence monitor settings
PRESENCE_PING_INTERVAL = 10  # seconds between pings in presence monitor
PRESENCE_DEBOUNCE = 3  # number of consistent checks required to flip state
PRESENCE_API_PORT = 8765  # port for presence HTTP status server
PRESENCE_LOG_FILE = "presence.log"

# Notification settings
NTFY_TOPIC = "is_my_garage_door_open"
NOTIFY_WHEN_SHUT = True

# Camera settings
CAM_URL = "http://192.168.0.225:8080/shot.jpg"

# Retry configuration for 503 errors
MAX_RETRIES = 15
RETRY_INTERVAL_SECONDS = 60

# Gemini query prompt
QUERY = """
I have a camera set up inside the garage to check if the garage door is open or closed.

In daytime, if the door is open, you should see the driveway and maybe the street.
Otherwise you'll see the inside of the door, maybe with light coming through the door 
windows.

At night, I'd expect a mostly black image if the door is shut. If it's open you might see 
the street lights outside.

Here's the latest photo.

Is the door open or closed?
"""
