import base64
import sys
import getpass

try:
    password = getpass.getpass('Enter password: ')
except Exception as error:
    print(error)
else:
    print(base64.b64encode(password.encode('ascii')).decode('ascii'))
