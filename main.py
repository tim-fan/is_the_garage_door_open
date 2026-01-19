from pydantic import BaseModel
from google import genai
from google.genai import types
import requests
import sys


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

if TEST_MODE:
    print("Running in TEST MODE")
    with open("door_open_daytime.jpg", "rb") as f:
        image_bytes = f.read()
    door_status = DoorStatus(is_open=True, rationale="test")
else:
    image_bytes = requests.get(CAM_URL).content
    image = types.Part.from_bytes(
      data=image_bytes, mime_type="image/jpeg"
    )

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

print(f"Door is open: {door_status.is_open}")
print(f"Rationale: {door_status.rationale}")

if door_status.is_open:
    headers={
        "Title": "Garage door is open!",
        "Priority": "urgent",
        "Tags": "warning,skull"
    }
else:
    headers={
        "Title": "garage door is shut",
        "Priority": "min",
        "Tags": "heavy_check_mark"
    }

if door_status.is_open or NOTIFY_WHEN_SHUT:
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=image_bytes,
        headers=headers
    )
