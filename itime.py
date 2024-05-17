import os
import os.path
import io
import json
import requests
from dotenv import load_dotenv
from dateutil import parser
from jira import JIRA, Issue
import base64
from requests_ntlm import HttpNtlmAuth
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta, date
from collections import defaultdict
from urllib.parse import urlparse
import click

load_dotenv()

jira_user_id = os.getenv('jira_user_id')

jira = JIRA(
    'https://ipsos-cx.atlassian.net/',
    basic_auth=(os.getenv('jira_user_email'), os.getenv('jira_api_token'))
)
jira_issue_id_key_map = {}

with io.open('jira_itime_task_mapping.json', 'r') as f:
    jira_itime_task_mapping = json.load(f)

jira_account_itime_mapping = {}

# create debug directory
if not os.path.exists('debug'):
    os.makedirs('debug')


def load_jira_account_itime_mapping():
    global jira_account_itime_mapping

    if not os.path.exists('debug/jira_account_mapping.json'):
        with io.open('debug/jira_account_mapping.json', 'w') as f:
            json.dump(jira_account_itime_mapping, f)
            return

    with io.open('debug/jira_account_mapping.json', 'r') as f:
        jira_account_itime_mapping = json.load(f)


def save_jira_account_mapping():
    with io.open('debug/jira_account_mapping.json', 'w') as f:
        json.dump(jira_account_itime_mapping, f)


jira_issue_tempo_account_custom_field = 'customfield_10032'

tempo_api_url = 'https://api.tempo.io/4'
tempo_token = os.getenv('tempo_api_token')

tempo_auth_headers = {
    'Authorization': f'Bearer {tempo_token}'
}

itime_base_url = 'https://itimes7.ipsos.com'
itime_url = '/iTime_CZ_SK/TmCrdForm.cfm'
itime_login_url = '/default.cfm?Debug=On&OpenType=Default&OpenID=0'
itime_home_url = '/iTime_CZ_SK/TmCrdForm.cfm'

itime_timesheet_create_url = '/iTime_CZ_SK/TmCrdEntry.CFM'  # ?TimeCard_ID=0
itime_timesheet_detail_url = '/iTime_CZ_SK/TmCrdEntry.CFM'  # param TimeCard_ID
itime_timesheet_save_url = '/iTime_CZ_SK/timecard_proc_v2.cfm'
itime_timesheet_submit_url = '/iTime_CZ_SK/timecard_proc_v2.cfm'

itime_projects_url = '/iTime_CZ_SK/Emp_PrjctAcsForm.cfm'
itime_projects_search_url = '/iTime_CZ_SK/Emp_PrjctAcsForm.CFM'
itime_projects_add_url = '/iTime_CZ_SK/EmplyPrjctAcsEntry.CFM'

itime_username = os.getenv('itime_username')
itime_password = base64.b64decode(os.getenv('itime_password_base_64').encode('ascii')).decode('ascii')

session = requests.Session()
session.auth = HttpNtlmAuth(itime_username, itime_password)
session.headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-GB,en;q=0.9',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
}

# login to itime

ITIME_DATE_FORMAT = '%d/%m/%Y'
TIME_CARD_DATE_REGEX = re.compile(r'\d{2}/\d{2}/\d{4}')

TEMPO_DATE_FORMAT = '%Y-%m-%d'

WEEK_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def debug_file(name: str, content: str):
    with io.open(name, 'w') as f:
        f.write(content)


def itime_request(method: str, url: str, **kwargs: any) -> requests.Response:
    response = session.request(method, itime_base_url + url, **kwargs)

    if 'debug_file' in kwargs:
        request_data = []

        for r in response.history:
            request_data.append(
                {
                    'url': r.request.url,
                    'body': r.request.body,
                    'headers': dict(r.request.headers),
                    'response': {
                        'status': r.status_code,
                        'headers': dict(r.headers),
                        'cookies': r.cookies.get_dict()
                    }
                }
            )

        debug_file(kwargs['debug_file'], json.dumps(request_data))

    return response


def itime_login():
    print('Logging into itime...')
    response = itime_request('GET', itime_url)
    url = urlparse(response.url)
    base_url = url.scheme + '://' + url.netloc

    if 'itimeAuths' in base_url:
        print('Cannot login.')
        print('Update your password in .env (needs to be base64 encoded)')
        exit(1)

    global itime_base_url
    itime_base_url = base_url


def check_jira_itime_task_mapping():
    tasks = set(list(jira_itime_task_mapping['issues'].values()) + list(jira_itime_task_mapping['projects'].values()))

    for task in tasks:
        if task not in jira_itime_task_mapping['task_names']:
            raise ValueError('task %s has not associated name in jira_itime_task_mapping.json' % task)


def get_tempo_worklogs(date_from: datetime, date_to: datetime):
    get_data = {
        'authorIds': [
            jira_user_id
        ],
        'from': date_from.strftime(TEMPO_DATE_FORMAT),
        'to': date_to.strftime(TEMPO_DATE_FORMAT)
    }

    response = requests.post(
        f'{tempo_api_url}/worklogs/search?limit=1000',
        headers=tempo_auth_headers,
        json=get_data
    )

    return response.json()['results']


def get_jira_issue_by_id(issue_id: str) -> Issue:
    if issue_id not in jira_issue_id_key_map:
        jira_issue_id_key_map[issue_id] = jira.issue(issue_id)

    return jira_issue_id_key_map[issue_id]


def get_task_for_issue(project_id: str, jira_issue: Issue) -> str:
    if jira_issue.key in jira_itime_task_mapping['issues']:
        return jira_itime_task_mapping['issues'][jira_issue.key]

    if project_id in jira_itime_task_mapping['projects']:
        return jira_itime_task_mapping['projects'][project_id]

    return jira_itime_task_mapping['default']


def get_jira_entries(date_from: datetime, date_to: datetime):
    print('Fetching jira time entries...')
    accounts = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(dict)
            )
        )
    )
    issue_account_map = {}

    def get_issue_account_and_task(issue_id: int):
        if issue_id not in issue_account_map:
            issue = get_jira_issue_by_id(str(issue_id))

            tempo_custom_field = issue.raw['fields'][jira_issue_tempo_account_custom_field]

            if tempo_custom_field is None:
                print('Jira issue %s has no associated account with it.' % issue.key)
                print('Do you want to enter it manually? Enter account name or leave blank to terminate and press '
                      'enter.')
                account_name = input('Account name: ')

                if account_name == '':
                    print('Exiting...')
                    exit(1)
            else:
                account_name = tempo_custom_field['value'].strip()

            issue_account_map[issue_id] = account_name

        return issue_account_map[issue_id]

    worklogs = get_tempo_worklogs(date_from, date_to)

    for worklog in worklogs:
        account = get_issue_account_and_task(worklog['issue']['id'])

        date_key = parser.parse(worklog['startDate']).strftime(ITIME_DATE_FORMAT)

        if date_key not in accounts[account]['entries']:
            accounts[account]['entries'][date_key] = 0

        if date_key not in accounts[account]['issues'][worklog['issue']['id']]:
            accounts[account]['issues'][worklog['issue']['id']][date_key] = 0

        accounts[account]['issues'][worklog['issue']['id']][date_key] += int(worklog['timeSpentSeconds'])
        accounts[account]['entries'][date_key] += int(worklog['timeSpentSeconds'])

    return accounts


def get_first_not_submitted_week() -> (str, date, date):
    response = itime_request('GET', itime_home_url)

    soup = BeautifulSoup(response.text, 'html5lib')

    # select existing timesheets
    time_sheet = None
    time_sheets = soup.select('form select[name="TimeCard_ID"] option:not([value="0"])')
    time_sheets.reverse()

    for option in time_sheets:
        if '(Submitted )' not in option.text:
            time_sheet = option
            break

    if time_sheet is None:
        print('create new sheet')
        # create new timesheet if not exists
        timesheet_detail_response = itime_request('GET', itime_timesheet_create_url, params={'TimeCard_ID': '0'})

        timesheet_soup = BeautifulSoup(timesheet_detail_response.text, 'html5lib')

        date_input = timesheet_soup.select_one('#cal-field-1')
        date_label = date_input.parent.select_one('font')

        match = TIME_CARD_DATE_REGEX.findall(date_label.text.strip())
        time_card_id = timesheet_soup.select_one('input[name="TmCrdID"]').attrs['value']
    else:
        match = TIME_CARD_DATE_REGEX.findall(time_sheet.text.strip())
        time_card_id = time_sheet.attrs['value']

    end = datetime.strptime(match[0], ITIME_DATE_FORMAT).date()
    start = end - timedelta(days=6)

    return time_card_id, start, end


PERSONAL_PROJECTS_LIST_ID = 'EmplyPrjct_Lst'
PROJECT_ID_REGEX = re.compile(r"(?:\d{2}-\d{6}(?:[\d-]+)?)|\d{8,}")

SEARCH_PROJECTS_LIST_ID = 'Prjct_Lst'


def find_and_add_itime_project(jira_account: str, project_id: str, existing_projects: dict[str, str]) -> str:
    response = itime_request('POST', itime_projects_search_url, data={
        'vExpandPPLFlag': 'N',
        'vExpandSFlag': 'Y',
        'Project_name': '',
        'Project_ID': project_id,
        'GetQProjects': 'Get Projects'
    })

    search_soup = BeautifulSoup(response.text, 'html5lib')

    project_list = search_soup.select('#' + SEARCH_PROJECTS_LIST_ID + ' option')

    if len(project_list) == 1 and project_list[0].attrs['value'] == '':
        project_list = []

    if len(project_list) != 1:
        if len(project_list) == 0:
            print('Project id "%s" not found for jira account %s' % (project_id, jira_account))
        else:
            print('Multiple projects found:')

            print('---')

            for project in project_list:
                print('%s (%s)' % (project.attrs['value'], project.text))

            print('---')

        project_id = input('Enter correct project id or empty to terminate: ')

        if project_id == '':
            print('Exiting...')
            exit(1)

        return find_and_add_itime_project(jira_account, project_id, existing_projects)

    project_id = project_list[0].attrs['value']

    jira_account_itime_mapping[jira_account] = project_id  # TODO: update account mapping file

    if project_id in existing_projects:
        return project_id

    print('Adding project "%s" to itime' % project_id)
    itime_request('POST', itime_projects_add_url, data={
        'vExpandPPLFlag': 'N',
        'vExpandSFlag': 'Y',
        'BU_ID': '0',
        'Project_Type': 'All',
        'Project_Name': '',
        'Client_Name': '',
        'Project_ID': project_id,
        'sortOrder1': 'JBNum',
        'sortOrder2': 'None',
        'sortOrder3': 'None',
        'Global': '0',
        'GlobalLEID': '',
        'Prjct_Lst': project_id,
        'MoveTo': '\xa0\xa0\xa0Add to personal list \xa0\xa0\xa0'
    })

    existing_projects[project_id] = project_id
    return project_id


def match_accounts_with_itime_projects(jira_accounts: list[str]) -> dict[str, str]:
    print('Matching jira accounts...')
    response = itime_request('GET', itime_projects_url, params={'TimeCard_ID': '0'})

    soup = BeautifulSoup(response.text, 'html5lib')

    project_list = soup.select_one('#' + PERSONAL_PROJECTS_LIST_ID)

    existing_projects = dict(
        list(
            map(
                lambda tag: (tag.attrs['value'], tag.attrs['value']),
                project_list.select('option')
            )
        )
    )
    existing_projects['Admin'] = 'Admin'

    existing_projects = {**existing_projects, **jira_account_itime_mapping}

    for jira_account in jira_accounts:
        project_id_match = re.findall(PROJECT_ID_REGEX, jira_account)

        if len(project_id_match) == 0:
            account_id = jira_account.split(' ')[0]
        else:
            account_id = project_id_match[0]

        if account_id not in existing_projects:
            itime_project_id = find_and_add_itime_project(jira_account, account_id, existing_projects)
            existing_projects[account_id] = itime_project_id

        existing_projects[jira_account] = existing_projects[account_id]

    return existing_projects


def format_seconds_for_itime(seconds: int) -> str:
    hours = seconds / 60 / 60
    return '%.2f' % hours


def group_jira_entries_by_account_and_task(entries: dict, account_mapping: dict[str, str]) -> dict[str, dict[str, any]]:
    account_task_entries = {}

    for jira_account, account_entry in entries.items():
        for issue_id, day_entries in account_entry['issues'].items():
            issue = get_jira_issue_by_id(issue_id)

            itime_project = account_mapping[jira_account]
            itime_task = get_task_for_issue(itime_project, issue)

            if itime_project not in account_task_entries:
                account_task_entries[itime_project] = {}

            if itime_task not in account_task_entries[itime_project]:
                account_task_entries[itime_project][itime_task] = {}

            for day_date, seconds in day_entries.items():
                if day_date not in account_task_entries[itime_project][itime_task]:
                    account_task_entries[itime_project][itime_task][day_date] = 0

                account_task_entries[itime_project][itime_task][day_date] += seconds

    return account_task_entries


def get_submit_form_default_data(time_card_id: str) -> dict[str, str]:
    response = itime_request('GET', itime_timesheet_detail_url, params={'TimeCard_ID': time_card_id})
    soup = BeautifulSoup(response.text, 'html5lib')

    form_data = {}
    inputs = soup.select('form input, form select, form textarea')

    for input_element in inputs:
        if 'name' not in input_element.attrs:
            continue

        input_value = ''
        if input_element.name == 'input' or input_element.name == 'textarea':
            if 'value' in input_element.attrs:
                input_value = input_element.attrs['value']
        elif input_element.name == 'select':
            selected = input_element.select_one('option[selected]')

            if selected is None:
                selected = input_element.select_one('option:first-child')

            if selected is not None and 'value' in selected.attrs:
                input_value = selected.attrs['value']

        form_data[input_element.attrs['name']] = input_value

    return form_data


def get_week_day_map(date_from: date) -> dict[str, str]:
    days = {}
    current_date = date_from
    i = 0
    while i < 7:
        days[current_date.strftime(ITIME_DATE_FORMAT)] = WEEK_DAYS[i]
        current_date += timedelta(days=1)
        i += 1

    return days


def validate_date_range(date_from: date, date_to: date):
    if date_from.weekday() != 0:  # Monday
        raise ValueError('Start date must be Monday')

    if date_to.weekday() != 6:  # Sunday
        raise ValueError('End date must be Sunday')

    delta = date_to - date_from
    if delta.days != 6:
        raise ValueError('Both dates must be within the same week')


def process_project_task(
        row_index: int,
        week_day_map: dict[str, str],
        form_data: dict[str, str],
        itime_project: str,
        itime_task: str,
        project_entries: dict[str, int]
) -> dict[str, int]:
    row_prefix = 'r' + str(row_index) + '_'

    form_data[row_prefix + 'PrjctCDName'] = ''
    form_data[row_prefix + 'Projname'] = itime_project
    form_data[row_prefix + 'Taskname'] = itime_task
    form_data[row_prefix + 'Taskname_Dscr'] = jira_itime_task_mapping['task_names'][itime_task]

    total_seconds = 0

    day_totals = {}

    for day_date, day in week_day_map.items():
        if day_date not in project_entries:
            form_data[row_prefix + day] = '0'
        else:
            form_data[row_prefix + day] = format_seconds_for_itime(project_entries[day_date])

        day_totals[day] = project_entries[day_date] if day_date in project_entries else 0

    form_data['tot2' + str(row_index)] = format_seconds_for_itime(total_seconds)

    return day_totals


def submit_report(
        time_card_id: str,
        date_from: date,
        date_to: date,
        entries: dict,
        account_mapping: dict[str, str]
):
    print('Creating itime report...')
    validate_date_range(date_from, date_to)

    form_data = get_submit_form_default_data(time_card_id)
    days = get_week_day_map(date_from)

    account_task_map = group_jira_entries_by_account_and_task(entries, account_mapping)

    day_totals = {}
    for day in days.values():
        day_totals[day] = 0

    row = 1
    for itime_project, task_entries in account_task_map.items():
        for itime_task, day_entries in task_entries.items():
            task_day_totals = process_project_task(row, days, form_data, itime_project, itime_task, day_entries)

            for day, seconds in task_day_totals.items():
                day_totals[day] += seconds

        row += 1

    form_data['TimeCardRowCount'] = str(row - 1)
    form_data['CurrentTotalRows'] = str(row - 1)

    day_index = 3
    for day_seconds in day_totals.values():
        day_seconds = format_seconds_for_itime(day_seconds)

        form_data['tot1_c' + str(day_index)] = day_seconds
        form_data['tot2_c' + str(day_index)] = day_seconds
        day_index += 1

    total = format_seconds_for_itime(sum(day_totals.values()))
    form_data['totHours1'] = total
    form_data['totHours2'] = total

    print('Saving report...')
    form_data['Save & ReCalculate'] = ''
    itime_request(
        'POST',
        itime_timesheet_save_url,
        data=form_data
    )
    form_data.pop('Save & ReCalculate')

    print('Submitting report...')
    form_data['Submit'] = ''
    itime_request(
        'POST',
        itime_timesheet_save_url,
        data=form_data
    )

    print('Report successfully submitted!')


def process():
    while True:
        time_card_id, from_date, to_date = get_first_not_submitted_week()

        today = date.today()
        if to_date > today and to_date.isocalendar().week != today.isocalendar().week:
            print('Nothing more to submit')
            return

        if not click.confirm('Do you want to create report for week %s - %s' % (from_date, to_date), default=True):
            print('Exiting...')
            return

        print('Creating report for week %s - %s' % (from_date, to_date))
        entries = get_jira_entries(from_date, to_date)
        account_mapping = match_accounts_with_itime_projects(list(entries.keys()))
        submit_report(time_card_id, from_date, to_date, entries, account_mapping)


if __name__ == '__main__':
    itime_login()
    load_jira_account_itime_mapping()
    check_jira_itime_task_mapping()
    process()
    save_jira_account_mapping()
