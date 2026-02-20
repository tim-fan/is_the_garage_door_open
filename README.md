# Is the garage door open?

| Door Shut | Door Open |
|-----------|-----------|
| ![Door Shut](door_shut_daytime.jpg) | ![Door Open](door_open_daytime.jpg) |

In the past, I may have left the house with the garage door open. Never again!

## Overview

* IP camera app runs on old Android phone, mounted in the garage
* this script runs continuously on a nuc on the same network
* script performs the actions:
    * fetch latest image from phone
    * send off to gemini, ask if the door is open
    * if open, send notification to my phone via ntfy
    * image is saved to a classification dataset structure (to enable training a more lightweight local model in future)
* intelligent timing ensures checks happen when needed while staying within daily API limits

## Check Timing Logic

The script runs continuously and checks conditions every 30 seconds to determine if it should query the Gemini API:

### Daytime (6am - 8pm)
- **Only checks once when leaving home**: Detects the transition from "someone home" → "nobody home"
- Pings configured phone IPs to determine presence
- Once the check runs after you leave, it won't check again until you return and leave again
- No checks while someone is home

### Night (8pm - 6am)
- **Scheduled checks at specific hours**: 8pm, 10pm, midnight, and 4am
- Each hour's check runs only once per night
- Checks run regardless of whether anyone is home

### Additional Safeguards
- **Daily API limit**: Maximum 20 API calls per day
- **503 retry logic**: If Gemini returns 503 Service Unavailable, retries up to 15 times (1 minute intervals)
- Resets counters at start of each new day

## Setup

Install dependencies with `uv`:
```bash
uv sync
```

## Configuration

Before running, configure the following:

1. **Gemini API key** - Set as environment variable:
```bash
export GEMINI_API_KEY=<your-api-key>
```
Find your API key at https://aistudio.google.com/app/apikey

2. **Phone IPs** - Edit `main.py` and update `PHONE_IPS` with your phones' static IP addresses:
```python
PHONE_IPS = {
    "Tim": "192.168.0.157",
    "Koi": "192.168.0.110",
}
```

3. **Timezone** - Edit `main.py` and set `LOCAL_TIMEZONE` to your local timezone:
```python
LOCAL_TIMEZONE = "America/Los_Angeles"  # PST/PDT
```
All time-based settings (daytime hours, night check times) are interpreted in this timezone, regardless of the system's timezone. Use standard [IANA timezone names](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).

4. **Optional settings** in `main.py`:
- `DAYTIME_START` / `DAYTIME_END`: Adjust daytime hours (default: 6am - 8pm in LOCAL_TIMEZONE)
- `NIGHT_CHECK_HOURS`: Change night check times (default: [20, 22, 0, 4] in LOCAL_TIMEZONE)
- `CHECK_INTERVAL_SECONDS`: How often to evaluate conditions (default: 30s)
- `MAX_API_CALLS_PER_DAY`: Daily API limit (default: 20)

## Usage

### Run the monitor
Start the continuous monitoring service:
```bash
uv run main.py
```

The script will run indefinitely, checking conditions and making API calls as needed. Press `Ctrl+C` to stop.

For systemd service setup, see the "Running as a Service" section below.

### Test mode
Run in test mode (uses local test image, skips presence detection):
```bash
uv run main.py --test
```

### View dataset

Once you've collected some images, view them in FiftyOne:
```bash
uv run view_dataset_fiftyone.py
```

This opens an interactive viewer showing all classified images organized by label (door_open/door_closed).

## Testing the Timing Logic

### Quick Unit Test

Run the included test script to verify the core timing logic:
```bash
uv run python test_timing_logic.py
```

This tests:
- Home → out transition detection
- Night check scheduling and tracking
- API rate limiting
- Realistic day scenario

### Manual Testing Approach

1. **Test daytime home→out transition**:
   ```bash
   # Temporarily set short daytime window for testing
   # In main.py, change: DAYTIME_START = time(0, 0) and DAYTIME_END = time(23, 59)
   uv run main.py
   ```
   - Watch the logs - should see "Someone is home during daytime" initially
   - Disconnect phones from WiFi or block their IPs temporarily
   - Within 30 seconds, should see "Detected home → out transition" and a check runs
   - Reconnect phones - should see "Already checked after going out" 
   - Disconnect again - should still see "Already checked after going out" (won't check again until you come home first)

2. **Test night checks**:
   ```bash
   # Temporarily modify NIGHT_CHECK_HOURS to include current hour + next hour
   # e.g., if it's 3pm: NIGHT_CHECK_HOURS = [15, 16, 17, 18]
   # And set DAYTIME_END = time(14, 0) to make it "night"
   uv run main.py
   ```
   - Should see check run at the specified hour
   - In same hour, should see "Already completed night check"
   - Wait for next hour, should run again

3. **Test API limits**:
   ```bash
   # Set MAX_API_CALLS_PER_DAY = 2
   # Trigger 2 checks, then should see "Daily API limit reached"
   ```

### Automated Testing

For more rigorous testing, you could:
- Mock the `datetime.now()` function to simulate different times
- Mock `is_phone_reachable()` to simulate presence changes
- Create unit tests for `PresenceTracker.should_check_now()` with various scenarios
- Use pytest with freezegun library to control time

### Monitor in Production

Watch the logs for patterns:
```bash
uv run main.py 2>&1 | tee garage_monitor.log
```

Look for:
- Proper transitions being detected
- Night checks happening at scheduled times
- API call counts staying under daily limit
- No unexpected check patterns

## Running as a Service

To run continuously as a systemd service, create `/etc/systemd/system/garage-monitor.service`:

```ini
[Unit]
Description=Garage Door Monitor
After=network.target

[Service]
Type=simple
User=<your-user>
WorkingDirectory=/path/to/is_the_garage_door_open
Environment="GEMINI_API_KEY=<your-api-key>"
ExecStart=/snap/bin/uv run main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then enable and start:
```bash
sudo systemctl enable garage-monitor
sudo systemctl start garage-monitor
sudo systemctl status garage-monitor
```

View logs:
```bash
sudo journalctl -u garage-monitor -f
```

## Notes
* tried moondream - only accepted one image per query, also slow CPU only, and got first query wrong, so switched to gemini
* script now runs continuously instead of cron for better control over timing logic