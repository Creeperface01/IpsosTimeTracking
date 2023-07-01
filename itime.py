import os
import requests
from dotenv import load_dotenv
from dateutil import parser
from jira import JIRA
import base64
from requests_ntlm import HttpNtlmAuth
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta

load_dotenv()

jira_user_id = os.getenv('jira_user_id')

jira = JIRA(
    'https://ipsos-cx.atlassian.net/',
    basic_auth=(os.getenv('jira_user_email'), os.getenv('jira_api_token'))
)

jira_issue_tempo_account_custom_field = 'customfield_10032'

tempo_api_url = 'https://api.tempo.io/4'
tempo_token = os.getenv('tempo_api_token')

tempo_auth_headers = {
    'Authorization': f'Bearer {tempo_token}'
}

itime_url = 'https://itimes7.ipsos.com/'
itime_login_url = 'https://itimeauths7.ipsos.com/default.cfm?Debug=On&OpenType=Default&OpenID=0'
itime_home_url = 'https://itimes7.ipsos.com/iTime_CZ_SK/TmCrdForm.cfm?TmCrdID=0'

itime_timesheet_create_url = 'https://itimes7.ipsos.com/iTime_CZ_SK/TmCrdEntry.CFM'
itime_timesheet_detail_url = 'https://itimes7.ipsos.com/iTime_CZ_SK/TmCrdDtlsChart.cfm'
itime_timesheet_submit_url = 'https://itimes7.ipsos.com/iTime_CZ_SK/timecard_proc_v2.cfm'

itime_username = os.getenv('itime_username')
itime_password = base64.b64decode(os.getenv('itime_password_base_64').encode('ascii')).decode('ascii')

session = requests.Session()
session.auth = HttpNtlmAuth(itime_username, itime_password)

ITIME_DATE_FORMAT = '%d/%M/%Y'
TIME_CARD_DATE_REGEX = re.compile(r'\d{2}/\d{2}/\d{4}')


def get_tempo_worklogs(date_from: datetime, date_to: datetime):
    get_data = {
        'accountId': jira_user_id,
        'from': date_from.isoformat(),
        'to': date_to.isoformat()
    }

    response = requests.get(
        f'{tempo_api_url}/worklogs',
        headers=tempo_auth_headers,
        json=get_data
    )

    return response.json()['results']


def get_jira_entries(date_from: datetime, date_to: datetime):
    accounts = {}
    issue_account_map = {}

    def get_issue_account(issue_id: int):
        if issue_id not in issue_account_map:
            issue = jira.issue(str(issue_id))
            issue_account_map[issue_id] = issue['jira_issue_tempo_account_custom_field']

        return issue_account_map[issue_id]

    worklogs = get_tempo_worklogs(date_from, date_to)

    for worklog in worklogs:
        account = get_issue_account(worklog['issue']['id'])

        if account not in accounts:
            accounts[account] = {}

        date_key = parser.parse(worklog['startDate']).strftime(ITIME_DATE_FORMAT)

        if date_key not in accounts[account]:
            accounts[account][date_key] = 0

        accounts[account][date_key] += worklog['timeSpentSeconds']

    return accounts


def get_first_not_submitted_week() -> (datetime, datetime):
    response = session.get(itime_home_url)

    soup = BeautifulSoup(response.text)

    # select existing timesheets
    time_sheet = soup.select_one('form select[name="TimeCard_ID"] option:not([value="0"]):last-child')

    if time_sheet is None:
        # create new timesheet if not exists
        timesheet_detail_response = session.get(itime_timesheet_create_url, params={'TimeCard_ID': 0})

        timesheet_soup = BeautifulSoup(timesheet_detail_response.text)
        match = TIME_CARD_DATE_REGEX.match(timesheet_soup.select_one('#cal-field-1 + font').text)
    else:
        match = TIME_CARD_DATE_REGEX.match(time_sheet.text)

    end = datetime.strptime(match.group(0), ITIME_DATE_FORMAT)
    start = end.date() - timedelta(days=6)

    return start, end


def submit_report():
    # TmCrdID: 338865
    # ChangedSbmt: Y
    # ChargeableHours: sChargeableHours
    # Save & ReCalculate:
    # MissingWkend: 1 / 1 / 1900
    # TmCrdID2: 338865
    # wk_end: 06 / 04 / 2023
    # dvsn_nm: 529202
    # TimeCardRowCount: 2
    # ConfiguredAddRows: 1
    # ChartWkEnd: 06 / 04 / 2023
    # ChangedDtls: Y
    # tot1_c3: 3.00
    # tot1_c4: 1.00
    # tot1_c5: 1.00
    # tot1_c6: 1.00
    # tot1_c7: 2.00
    # tot1_c8: 0.00
    # tot1_c9: 0.00
    # totHours1: 8.00
    # r1_PrjctCDName:
    # r1_Projname: Admin
    # r1_Taskname: N0010
    # r1_Taskname_Dscr: Administrativa
    # a
    # management
    # r1_Monday: 2.00
    # r1_Tuesday: 0.00
    # r1_Wednesday: 0.00
    # r1_Thursday: 1.00
    # r1_Friday: 1.00
    # r1_Saturday: 0.00
    # r1_Sunday: 0.00
    # tot21: 4.00
    # r2_PrjctCDName:
    # r2_Projname: P29239002
    # r2_Taskname: N0003
    # r2_Taskname_Dscr: P
    # projekty
    # r2_Monday: 1.00
    # r2_Tuesday: 0.00
    # r2_Wednesday: 1.00
    # r2_Thursday: 0.00
    # r2_Friday: 0.00
    # r2_Saturday: 0.00
    # r2_Sunday: 0.00
    # tot22: 2.00
    # DSNGlobal: iTime_CZ_SK
    # r3_PrjctCDName:
    # r3_Projname: Admin
    # r3_Taskname: N0009
    # r3_Taskname_Dscr:
    # r3_Monday: 0.00
    # r3_Tuesday: 1
    # r3_Wednesday: 0.00
    # r3_Thursday: 0.00
    # r3_Friday: 1
    # r3_Saturday: 0.00
    # r3_Sunday: 0.00
    # tot23: 2.00
    # tot2h3: 0.00
    # DSNGlobal: iTime_CZ_SK
    # r4_PrjctCDName:
    # r4_Projname: Select
    # a
    # Project
    # from your list
    # r4_Taskname:
    # r4_Taskname_Dscr:
    # r4_Monday: 0.00
    # r4_Tuesday: 0.00
    # r4_Wednesday: 0.00
    # r4_Thursday: 0.00
    # r4_Friday: 0.00
    # r4_Saturday: 0.00
    # r4_Sunday: 0.00
    # tot24: 0.00
    # tot2h4: 0.00
    # CurrentTotalRows: 4
    # tot2_c3: 3.00
    # tot2_c4: 1.00
    # tot2_c5: 1.00
    # tot2_c6: 1.00
    # tot2_c7: 2.00
    # tot2_c8: 0.00
    # tot2_c9: 0.00
    # totHours2: 8.00
    # Chargeability: Chargeability
    # Rate: 0 %
    # TmSht_Comments:
    pass
