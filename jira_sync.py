import os

import requests
import io
import json
from dateutil import parser
from dotenv import load_dotenv
from jira import JIRA
from jira.exceptions import JIRAError

load_dotenv()

jira = JIRA(
    'https://ipsos-cx.atlassian.net/',
    basic_auth=(os.getenv('jira_user_email'), os.getenv('jira_api_token'))
)

user_id = os.getenv('jira_user_id')

tempo_api_url = 'https://api.tempo.io/4'
tempo_token = os.getenv('tempo_api_token')

auth_headers = {
    'Authorization': f'Bearer {tempo_token}'
}

with io.open('toggl-parsed.json', 'r') as f:
    data = json.load(f)

issues = {}

issue_key_replacements = {}


def get_issue_id(issue_key: str) -> int:
    issue_key = issue_key.upper()

    if issue_key in issue_key_replacements:
        issue_key = issue_key_replacements[issue_key]

    if issue_key not in issues:
        old_issue_key = issue_key
        while True:
            try:
                issue = jira.issue(issue_key)
                issues[issue.key] = int(issue.id)
                break
            except JIRAError as error:
                print(error.text)
                print('Issue with issue key %s does not exist' % issue_key)
                issue_key = input('Enter issue key manually: ')
                issue_key_replacements[old_issue_key] = issue_key

    return issues[issue_key]


for entry in data:
    tag = entry['tag']
    start_date = parser.parse(entry['date'])
    minutes = entry['minutes']
    description = entry['description']

    if description is None:
        description = ''

    print('Posting [%s] - %s - %s' % (start_date.strftime('%Y-%m-%d %H:%M:%S'), tag, description))

    post_data = {
        'authorAccountId': user_id,
        'description': description,
        'issueId': get_issue_id(tag),
        'timeSpentSeconds': minutes * 60,
        'startDate': start_date.strftime('%Y-%m-%d'),
        'startTime': start_date.strftime('%H:%M:%S')
    }

    response = requests.post(
        f'{tempo_api_url}/worklogs',
        headers=auth_headers,
        json=post_data
    )
