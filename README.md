# Is the garage door open?

| Door Shut | Door Open |
|-----------|-----------|
| ![Door Shut](door_shut_daytime.jpg) | ![Door Open](door_open_daytime.jpg) |

In the past, I may have left the house with the garage door open. Never again!

## Overview

Monitors garage door via camera + AI with smart timing to stay within free API limits:

- **Hardware**: Old Android phone running IP camera app, mounted in garage
- **Presence detection**: Separate process pings phones to detect when you're home (with debouncing to avoid false positives)
- **Smart timing**: Only checks door when you leave (daytime) or at scheduled hours (night)
- **Gemini Vision**: Analyzes camera image to determine if door is open
- **Notifications**: Sends alerts via ntfy if door is left open
- **Dataset**: Saves classified images for potential future local model training

## How It Works

### Daytime (6am - 8pm)
- Monitors phone presence via WiFi pings
- Checks door **once** when everyone leaves (home → away transition)
- Won't check again until someone returns home first
- Prevents wasteful API calls while you're home

### Night (8pm - 6am)  
- Scheduled checks at: **8pm, 10pm, midnight, 4am**
- Each check runs once per night regardless of presence
- Ensures door is closed before bed and overnight

### Safeguards
- **20 API calls/day max** (well within free tier limits)
- **503 retry**: Up to 15 retries if Gemini is temporarily unavailable
- **Graceful fallback**: If presence service is down, falls back to direct pings

## Setup

1. **Install dependencies:**
   ```bash
   uv sync
   ```

2. **Configure settings** in `config.py`:
   - `PHONE_IPS`: Your phones' static IP addresses
   - `LOCAL_TIMEZONE`: Your timezone (e.g., "America/Los_Angeles")
   - `DAYTIME_START` / `DAYTIME_END`: Daytime hours (default 6am-8pm)
   - `NIGHT_CHECK_HOURS`: Night check times (default [20, 22, 0, 4])
   - `CAM_URL`: IP camera URL
   - `NTFY_TOPIC`: Your ntfy.sh topic name

3. **Set Gemini API key:**
   ```bash
   export GEMINI_API_KEY=<your-api-key>
   ```
   Get your key at https://aistudio.google.com/app/apikey

## Usage

### Run manually:
```bash
# Start presence monitor (runs in background)
python3 presence_monitor.py &

# Start garage monitor
uv run main.py
```

### Test mode:
```bash
uv run main.py --test  # Uses local test image, skips presence detection
```

### View collected images:
```bash
uv run view_dataset_fiftyone.py  # Opens interactive viewer
```

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

## Running as a Service (systemd)

**Recommended for production use.**

1. **Run the install script:**
   ```bash
   cd systemd && ./install.sh
   ```

2. **Create environment file:**
   ```bash
   mkdir -p ~/.config/garage-monitor
   cp systemd/env.example ~/.config/garage-monitor/env
   nano ~/.config/garage-monitor/env  # Add your GEMINI_API_KEY
   chmod 600 ~/.config/garage-monitor/env
   ```

3. **Update paths in service files if needed:**
   ```bash
   sudo nano /etc/systemd/system/presence-monitor.service
   sudo nano /etc/systemd/system/garage-monitor.service
   ```

4. **Enable and start:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable presence-monitor garage-monitor
   sudo systemctl start presence-monitor garage-monitor
   ```

5. **Monitor logs:**
   ```bash
   sudo journalctl -u garage-monitor -f
   sudo journalctl -u presence-monitor -f
   ```

### Architecture

Two systemd services work together:

- **`presence-monitor`**: Pings phones every 10s, debounces state (requires 3 consistent checks), exposes HTTP API on port 8765
- **`garage-monitor`**: Main process that queries presence service and checks garage door based on timing logic

The garage monitor depends on the presence monitor but will fall back to direct pings if it's unavailable.

## Notes
* tried moondream - only accepted one image per query, also slow CPU only, and got first query wrong, so switched to gemini
* script now runs continuously instead of cron for better control over timing logic