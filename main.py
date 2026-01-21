from pydantic import BaseModel
from google import genai
from google.genai import types
import requests
import sys
import os
from pathlib import Path
from datetime import datetime


# Check for test mode
TEST_MODE = "--test" in sys.argv
NTFY_TOPIC="is_my_garage_door_open"
CAM_URL="http://192.168.0.225:8080/shot.jpg"
NOTIFY_WHEN_SHUT=False

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

# Setup dataset directory
SCRIPT_DIR = Path(__file__).parent
DATASET_DIR = SCRIPT_DIR / "dataset"
DATASET_OPEN_DIR = DATASET_DIR / "door_open"
DATASET_CLOSED_DIR = DATASET_DIR / "door_closed"

def init_dataset_dirs():
    """Initialize dataset directory structure if it doesn't exist."""
    DATASET_OPEN_DIR.mkdir(parents=True, exist_ok=True)
    DATASET_CLOSED_DIR.mkdir(parents=True, exist_ok=True)

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
    Get current status.

    Return [DoorStatus, image_bytes, error_state] tuple

    (on error, error_state will be true, and
    error message is provided in door_status.rationale)
    """
    error_state = False
    image_bytes = bytes()
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

    except Exception as e:
        error_message = f"Error: {str(e)}"
        print(error_message)
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
    

get_status = get_door_status if not TEST_MODE else get_door_status_test_mode
door_status, image_bytes, is_error = get_status()

print(f"Door is open: {door_status.is_open}")
print(f"Rationale: {door_status.rationale}")

# Save to dataset only on successful classification (not in test mode, not on error)
if not TEST_MODE and not is_error and image_bytes:
    init_dataset_dirs()
    save_to_dataset(image_bytes, door_status.is_open)

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
else:
    # door is shut, no need to notify
    pass
