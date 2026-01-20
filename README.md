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
* script runs on a cron job at specified timings, chosen to stay within daily free tier limits for gemini

## Notes
* before running `export GEMINI_API_KEY=<secret>`
    * find key at https://aistudio.google.com/app/apikey
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