import os
import io
import json
import requests
from dotenv import load_dotenv
from dateutil import parser
from jira import JIRA
import base64
from requests_ntlm import HttpNtlmAuth
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
from collections import defaultdict

load_dotenv()

itime_home_url = 'https://itimes7.ipsos.com/iTime_CZ_SK/TmCrdForm.cfm?TmCrdID=0'
itime_projects_url = 'https://itimes7.ipsos.com/iTime_CZ_SK/Emp_PrjctAcsForm.cfm'

itime_username = os.getenv('itime_username')
itime_password = base64.b64decode(os.getenv('itime_password_base_64').encode('ascii')).decode('ascii')

session = requests.Session()
session.auth = HttpNtlmAuth(itime_username, itime_password)
session.headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-GB,en;q=0.9',
    # 'Cache-Control': 'no-cache',
    # 'Pragma': 'no-cache',
    # 'Sec-Ch-Ua': '"Not.A/Brand";v="8", "Chromium";v="114", "Google Chrome";v="114"',
    # 'Sec-Ch-Ua-Mobile': '?0',
    # 'Sec-Ch-Ua-Platform': '"macOS"',
    # 'Sec-Fetch-Sest': 'document',
    # 'Sec-Fetch-Mode': 'navigate',
    # 'Sec-Fetch-Site': 'none',
    # 'Sec-Fetch-User': '?1',
    # 'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
}


def debug_file(name: str, content: str):
    with io.open(name, 'w') as f:
        f.write(content)


session.get(itime_home_url)

session.cookies.set('CFCLIENT_ITIME', '""')

response = session.get(itime_projects_url)
debug_file('itime_debug.html', response.text)

for r in response.history:
    print(r.request.url)
    print(r.status_code)
    print(r.request.headers)
    print(r.headers)
    print('-------------------')