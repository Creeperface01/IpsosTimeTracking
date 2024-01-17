import json
import os

import requests
import io
import re
from base64 import b64encode
from dateutil import parser
from dotenv import load_dotenv

load_dotenv()

start_date = '2023-12-01'
end_date = '2024-01-01'


def round_minutes(v_minutes: int) -> int:
    if 15 > v_minutes > 2:
        return 15

    mod = v_minutes % 15
    floored = v_minutes - mod

    if mod > 5:
        floored += 15

    return floored


issue_pattern = re.compile(r'^(?:#\d+\s+)?(?:([a-z]+-\d+)|(?:\[([a-z]+-\d+)])|(?:hotfix|feature)(?:\s+-\s+|/)([a-z]+[- ]\d+))(\D.*)?',
                           re.IGNORECASE)
tag_pattern = re.compile(r'^\w+-\d+$')

api_token = os.getenv('toggl_api_token')

response = requests.get(
    'https://api.track.toggl.com/api/v9/me/time_entries',
    headers={
        'content-type': 'application/json',
        'Authorization': 'Basic %s' % b64encode(f"{api_token}:api_token".encode('ascii')).decode("ascii")
    },
    params={
        'start_date': start_date,
        'end_date': end_date
    }
)

data = response.json()

entries = []
for entry in data:
    match = issue_pattern.match(entry['description'])

    if match is None:
        print(f"Could not match issue tag for description: '{entry['description']}' logged: {entry['start']}")
        tag = input('Enter tag manually: ')
        description = input('Enter tag description: ')
    else:
        tag = match.group(1)

        if tag is None:
            tag = match.group(2)

        if tag is None:
            tag = match.group(3)

        description = match.group(4)

    if ' ' in tag:
        tag = tag.replace(' ', '-')

    if tag_pattern.match(tag) is None:
        print(f"Could not match issue tag for description: '{entry['description']}' logged: {entry['start']}")
        tag = input('Enter tag manually: ')
        description = input('Enter tag description: ')

    start = parser.isoparse(entry['start'])
    stop = parser.isoparse(entry['stop'])

    if start.date() != stop.date():
        raise ValueError(f"Invalid date range - {entry['start']} - {entry['stop']}")

    minutes = int((stop - start).total_seconds() / 60)
    minutes = round_minutes(minutes)

    if minutes == 0:
        continue

    if description is not None:
        description = description.strip()

    entries.append({
        'tag': tag,
        'date': start,
        'minutes': minutes,
        'description': description
    })

entries.sort(key=lambda x: x['date'])

with io.open('toggl-parsed.json', 'w') as f:
    f.write(json.dumps(entries, default=str, ensure_ascii=False))
