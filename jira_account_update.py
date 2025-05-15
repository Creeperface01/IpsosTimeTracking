import os
import time

import requests
import io
import json
from dotenv import load_dotenv
from jira import JIRA
import enquiries
import pendulum

ACCOUNT_FIELD = 'customfield_10032'

load_dotenv()

jira = JIRA(
    'https://ipsos-cx.atlassian.net/',
    basic_auth=(os.getenv('jira_user_email'), os.getenv('jira_api_token'))
)

tempo_api_url = 'https://api.tempo.io/4'
tempo_token = os.getenv('tempo_api_token')
tempo_auth_headers = {
    'Authorization': f'Bearer {tempo_token}',
    "Accept": "application/json",
    "Content-Type": "application/json"
}

user_id = os.getenv('jira_user_id')


def get_all_tempo_account_key_id_mapping(keys: list):
    response = requests.post(
        f'{tempo_api_url}/accounts/search',
        headers=tempo_auth_headers,
        params={
            'limit': 500
        },
        json={
            'keys': keys
        }
    )

    mapping = {}
    accounts = response.json()

    for account in accounts['results']:
        mapping[account['key']] = account['id']

    return mapping


def search_all_issues(jql_query: str, batch_size: int = 100):
    start_at = 0

    while True:
        issues = jira.search_issues(jql_query, startAt=start_at, maxResults=batch_size)

        if not issues:
            break

        yield from issues

        start_at += len(issues)

        if len(issues) < batch_size:
            break

        time.sleep(0.5) # avoid rate limiting


def update_issues(date_from: str):
    with io.open('account_update_mapping.json', 'r') as f:
        account_map = json.load(f)

    account_key_id_map = get_all_tempo_account_key_id_mapping(
        list(account_map.values())
    )

    for (account_from, account_to) in account_map.items():
        print(f'Updating account {account_from} to {account_to}')

        account_to_id = account_key_id_map[account_to]

        query = f'Account.key = {account_from} AND worklogDate > {date_from}'
        issues = search_all_issues(query)

        for issue in issues:
            print(f'Updating issue {issue.key}')
            issue.update(fields={ACCOUNT_FIELD: account_to_id})


def choose_date():
    options = [
        'This week',
        'Last week',
        'This month',
        'Last month',
        'Custom',
    ]
    choice = enquiries.choose('Select a date - only issues with a newer worklog will be included. ', options)

    now = pendulum.now()

    start_date = None

    if choice == 'This week':
        start_date = now.start_of('week')
    elif choice == 'Last week':
        start_date = now.subtract(weeks=1).start_of('week')
    elif choice == 'This month':
        start_date = now.start_of('month')
    elif choice == 'Last month':
        start_date = now.subtract(months=1).start_of('month')
    elif choice == 'Custom':
        start_date = pendulum.from_format(input('Enter starting date (YYYY-MM-DD): '), 'YYYY-MM-DD')

        if start_date is None:
            print('Invalid start date')
            exit(1)

    return start_date.strftime('%Y-%m-%d')


if __name__ == '__main__':
    update_issues(choose_date())
