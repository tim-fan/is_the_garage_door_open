# Is the garage door open?

| Door Shut | Door Open |
|-----------|-----------|
| ![Door Shut](door_shut_daytime.jpg) | ![Door Open](door_open_daytime.jpg) |

In the past, I may have left the house with the garage door open. Never again!

## Overview

* IP camera app runs on old Android phone, mounted in the garage
* this script runs on a nuc on the same network
* script performs the actions:
    * fetch latest image from phone
    * send off to gemini, ask if the door is open
    * if open, send notification to my phone via ntfy
    * image is saved to a classification dataset structure (to enable training a more lightweight local model in future)
* script runs on a cron job at specified timings, chosen to stay within daily free tier limits for gemini

## Setup

Install dependencies with `uv`:
```bash
uv sync
```

## Configuration

Before running, set your Gemini API key:
```bash
export GEMINI_API_KEY=<your-api-key>
```

Find your API key at https://aistudio.google.com/app/apikey

## Usage

### Run classification
```bash
uv run main.py
```

Run in test mode (uses local test image, skips network fetch and Gemini):
```bash
uv run main.py --test
```

### View dataset

Once you've collected some images, view them in FiftyOne:
```bash
uv run view_dataset_fiftyone.py
```

This opens an interactive viewer showing all classified images organized by label (door_open/door_closed).

## Notes
* tried moondream - only accepted one image per query, also slow CPU only, and got first query wrong, so switched to gemini


## Crontab example

Runs 20 times a day (free tier gives 20 requests per day), distributed to check more often around midday.

```
GEMINI_API_KEY=<ADD_SECRET_KEY_HERE>

# 1. Top of the hour: 1am, 6am-12pm, 1pm-6pm, 8pm, 10pm (16 requests)
0 1,6,7,8,9,10,11,12,13,14,15,16,17,18,20,22 * * * /snap/bin/uv --directory /path/to/project/is_the_garage_door_open run main.py > /tmp/garage_door_check.log 2>&1

# 2. Half-past marks: 12:30pm, 1:30pm, 2:30pm, 3:30pm (4 requests)
30 12,13,14,15 * * * /snap/bin/uv --directory /path/to/project/is_the_garage_door_open run main.py > /tmp/garage_door_check.log 2>&1
```