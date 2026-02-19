from pydantic import BaseModel
from google import genai
from google.genai import types
import requests
import sys
import os
from pathlib import Path
from datetime import datetime, time
import time as time_module
import subprocess


# Check for test mode
TEST_MODE = "--test" in sys.argv
NTFY_TOPIC="is_my_garage_door_open"
CAM_URL="http://192.168.0.225:8080/shot.jpg"
NOTIFY_WHEN_SHUT=True

# Configuration for presence detection and daytime hours
PHONE_IPS = {
    "Tim": "192.168.0.157",
    "Koi": "192.168.0.110",
}
DAYTIME_START = time(6, 0)  # 6:00 AM
DAYTIME_END = time(20, 0)   # 8:00 PM

# Retry configuration for 503 errors
MAX_RETRIES = 15
RETRY_INTERVAL_SECONDS = 60

# Continuous monitoring configuration
CHECK_INTERVAL_SECONDS = 30  # How often to check if we should run the door check
MAX_API_CALLS_PER_DAY = 20

# Night check times (hours in 24-hour format)
NIGHT_CHECK_HOURS = [20, 22, 0, 4]  # 8pm, 10pm, midnight, 4am

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

class DoorStatus(BaseModel):
    is_open: bool
    rationale: str

class ApiRateLimiter:
    """Manages API call timing and daily limits."""
    
    def __init__(self, max_calls_per_day: int):
        self.max_calls_per_day = max_calls_per_day
        self.api_calls_today: int = 0
        self.current_day: int | None = None
    
    def _reset_if_new_day(self):
        """Reset daily counter if it's a new day."""
        today = datetime.now().day
        if self.current_day != today:
            self.current_day = today
            self.api_calls_today = 0
            print(f"New day detected, reset API call counter")
    
    def can_make_api_call(self) -> bool:
        """Check if we can make an API call based on daily limits."""
        self._reset_if_new_day()
        
        # Check daily limit
        if self.api_calls_today >= self.max_calls_per_day:
            print(f"Daily API limit reached ({self.api_calls_today}/{self.max_calls_per_day})")
            return False
        
        return True
    
    def record_api_call(self):
        """Record that an API call was made."""
        self.api_calls_today += 1
        print(f"API call recorded. Calls today: {self.api_calls_today}/{self.max_calls_per_day}")


class PresenceTracker:
    """Tracks presence state and determines when to run checks."""
    
    def __init__(self, night_check_hours: list[int]):
        self.someone_was_home: bool = True  # Default to True so first "nobody home" triggers a check
        self.night_check_hours = set(night_check_hours)
        self.completed_night_checks: set[int] = set()
    
    def _reset_night_checks_if_new_day(self):
        """Reset night check tracking at start of new day."""
        current_hour = datetime.now().hour
        # Reset at 6am (start of new cycle)
        if current_hour == 6 and self.completed_night_checks:
            print("New day (6am), resetting night check tracking")
            self.completed_night_checks.clear()
    
    def should_check_now(self, someone_home: bool, is_daytime: bool) -> tuple[bool, str]:
        """
        Determine if we should run a check now.
        Returns (should_check, reason).
        """
        self._reset_night_checks_if_new_day()
        current_hour = datetime.now().hour
        
        # During daytime: only check on home -> out transition
        if is_daytime:
            if self.someone_was_home and not someone_home:
                # Transition: home -> out
                self.someone_was_home = someone_home
                return True, "Detected home -> out transition"
            
            # Update state
            self.someone_was_home = someone_home
            
            if someone_home:
                return False, "Someone is home during daytime"
            else:
                return False, "Already checked after going out"
        
        # At night: check at specific hours (once per hour)
        else:
            # Update presence state
            self.someone_was_home = someone_home
            
            if current_hour in self.night_check_hours:
                if current_hour not in self.completed_night_checks:
                    self.completed_night_checks.add(current_hour)
                    return True, f"Night check at {current_hour}:00"
                else:
                    return False, f"Already completed night check for {current_hour}:00"
            else:
                return False, f"Not a night check hour (current: {current_hour}:00)"
        
        return False, "Unknown state"


# Setup dataset directory
SCRIPT_DIR = Path(__file__).parent
DATASET_DIR = SCRIPT_DIR / "dataset"
DATASET_OPEN_DIR = DATASET_DIR / "door_open"
DATASET_CLOSED_DIR = DATASET_DIR / "door_closed"

def init_dataset_dirs():
    """Initialize dataset directory structure if it doesn't exist."""
    DATASET_OPEN_DIR.mkdir(parents=True, exist_ok=True)
    DATASET_CLOSED_DIR.mkdir(parents=True, exist_ok=True)

def is_phone_reachable(ip: str) -> bool:
    """Check if a phone is reachable via ping."""
    try:
        # Use ping with 1 second timeout, 1 packet
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "1", ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, Exception):
        return False

def is_anyone_home() -> bool:
    """Check if any phone is reachable."""
    people_home = []
    for name, ip in PHONE_IPS.items():
        if is_phone_reachable(ip):
            people_home.append(name)
    
    if people_home:
        print(f"Someone is home: {', '.join(people_home)}")
        return True
    else:
        print("No phones reachable - nobody home")
        return False

def is_daytime() -> bool:
    """Check if current time is within daytime hours."""
    current_time = datetime.now().time()
    is_day = DAYTIME_START <= current_time <= DAYTIME_END
    return is_day

def should_run_door_check(api_limiter: ApiRateLimiter, presence_tracker: PresenceTracker) -> tuple[bool, str]:
    """
    Determine if we should run the door check now.
    Returns (should_check, reason).
    """
    if TEST_MODE:
        return True, "Test mode"
    
    # Check if we've hit daily API limit
    if not api_limiter.can_make_api_call():
        return False, "Daily API limit reached"
    
    # Check if someone is home
    someone_home = is_anyone_home()
    
    # Check if it's daytime
    daytime = is_daytime()
    
    # Delegate to presence tracker for the logic
    should_check, reason = presence_tracker.should_check_now(someone_home, daytime)
    
    return should_check, reason


def save_to_dataset(image_bytes: bytes, is_open: bool):
    """Save image to appropriate dataset folder."""
    if is_open:
        save_dir = DATASET_OPEN_DIR
    else:
        save_dir = DATASET_CLOSED_DIR
    
    # Use timestamp for unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    filename = f"{timestamp}.jpg"
    filepath = save_dir / filename
    
    with open(filepath, "wb") as f:
        f.write(image_bytes)
    
    print(f"Saved image to {filepath}")

def get_door_status() -> tuple[DoorStatus, bytes, bool]:
    """
    Get current status with retry logic for 503 errors.

    Return [DoorStatus, image_bytes, error_state] tuple

    (on error, error_state will be true, and
    error message is provided in door_status.rationale)
    """
    error_state = False
    image_bytes = bytes()
    
    for attempt in range(MAX_RETRIES + 1):
        try:
            # fetch image
            response = requests.get(CAM_URL)
            response.raise_for_status()
            image_bytes = response.content
            image = types.Part.from_bytes(
              data=image_bytes, mime_type="image/jpeg"
            )

            # call gemini
            client = genai.Client()
            response = client.models.generate_content(
                model="gemini-3-flash-preview",
                contents=[QUERY, image],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": DoorStatus,
                }
            )
            # Access the parsed Pydantic object directly
            door_status = response.parsed
            
            if door_status is None:
                raise ValueError(f"Failed to parse gemini response: {response}")
            
            # Success! Return the result
            return door_status, image_bytes, error_state

        except requests.exceptions.HTTPError as e:
            # Check if it's a 503 error
            if e.response is not None and e.response.status_code == 503:
                if attempt < MAX_RETRIES:
                    print(f"503 Service Unavailable (attempt {attempt + 1}/{MAX_RETRIES + 1}). Retrying in {RETRY_INTERVAL_SECONDS} seconds...")
                    time_module.sleep(RETRY_INTERVAL_SECONDS)
                    continue
                else:
                    error_message = f"Error: 503 Service Unavailable persisted after {MAX_RETRIES + 1} attempts over {MAX_RETRIES} minutes"
                    print(error_message)
                    door_status = DoorStatus(
                        is_open=False,
                        rationale=error_message
                    )
                    error_state = True
                    return door_status, image_bytes, error_state
            else:
                # Other HTTP error, don't retry
                error_message = f"HTTP Error: {str(e)}"
                print(error_message)
                door_status = DoorStatus(
                    is_open=False,
                    rationale=error_message
                )
                error_state = True
                return door_status, image_bytes, error_state
                
        except Exception as e:
            # Non-503 error, don't retry
            error_message = f"Error: {str(e)}"
            print(error_message)
            door_status = DoorStatus(
                is_open=False,
                rationale=error_message
            )
            error_state = True
            return door_status, image_bytes, error_state
    
    # This should never be reached, but just in case
    error_message = "Unexpected error: max retries reached without resolution"
    door_status = DoorStatus(
        is_open=False,
        rationale=error_message
    )
    error_state = True
    return door_status, image_bytes, error_state


def get_door_status_test_mode():
    print("Running in TEST MODE")
    with open("door_open_daytime.jpg", "rb") as f:
        image_bytes = f.read()
    door_status = DoorStatus(is_open=True, rationale="test")
    return door_status, image_bytes, False

def send_notification(door_status: DoorStatus, image_bytes: bytes, is_error: bool):
    """Send notification via ntfy."""
    ntfy_url = f"https://ntfy.sh/{NTFY_TOPIC}"
    
    if is_error:
        requests.post(
            ntfy_url,
            data=door_status.rationale.encode(encoding='utf-8'),
            headers={
                "Title": "Garage door check failed",
                "Priority": "default",
                "Tags": "facepalm"
            }
        )
    elif door_status.is_open:
        requests.post(
            ntfy_url,
            data=image_bytes,
            headers={
                "Title": "Garage door is open!",
                "Priority": "urgent",
                "Tags": "warning,skull"
            }
        )
    elif NOTIFY_WHEN_SHUT:
        requests.post(
            ntfy_url,
            data=image_bytes,
            headers={
                "Title": "garage door is shut",
                "Priority": "min",
                "Tags": "heavy_check_mark"
            }
        )

def run_door_check_cycle(api_limiter: ApiRateLimiter):
    """Run one cycle of the door check."""
    get_status = get_door_status if not TEST_MODE else get_door_status_test_mode
    door_status, image_bytes, is_error = get_status()

    print(f"Door is open: {door_status.is_open}")
    print(f"Rationale: {door_status.rationale}")

    # Record API call
    api_limiter.record_api_call()

    # Save to dataset only on successful classification (not in test mode, not on error)
    if not TEST_MODE and not is_error and image_bytes:
        init_dataset_dirs()
        save_to_dataset(image_bytes, door_status.is_open)

    # Send notification
    send_notification(door_status, image_bytes, is_error)

def main():
    """Main continuous monitoring loop."""
    print("Starting garage door monitor...")
    print(f"Configuration:")
    print(f"  - Check interval: {CHECK_INTERVAL_SECONDS}s")
    print(f"  - Max API calls per day: {MAX_API_CALLS_PER_DAY}")
    print(f"  - Daytime hours: {DAYTIME_START} - {DAYTIME_END}")
    print(f"  - Night check hours: {sorted(NIGHT_CHECK_HOURS)}")
    print(f"  - Phone IPs: {PHONE_IPS}")
    print(f"  - Test mode: {TEST_MODE}")
    print()
    print("Check Logic:")
    print(f"  - Daytime: Check once when 'home -> out' transition detected")
    print(f"  - Night: Check at specified hours ({', '.join(f'{h}:00' for h in sorted(NIGHT_CHECK_HOURS))})")
    print()
    
    api_limiter = ApiRateLimiter(MAX_API_CALLS_PER_DAY)
    presence_tracker = PresenceTracker(NIGHT_CHECK_HOURS)
    
    while True:
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] Checking conditions...")
            
            should_check, reason = should_run_door_check(api_limiter, presence_tracker)
            print(f"  -> {reason}")
            
            if should_check:
                print("Running door check...")
                run_door_check_cycle(api_limiter)
            
            print(f"Waiting {CHECK_INTERVAL_SECONDS}s until next check...")
            print()
            time_module.sleep(CHECK_INTERVAL_SECONDS)
            
        except KeyboardInterrupt:
            print("\nShutting down garage door monitor...")
            break
        except Exception as e:
            print(f"Unexpected error in main loop: {e}")
            print(f"Waiting {CHECK_INTERVAL_SECONDS}s before retry...")
            time_module.sleep(CHECK_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
