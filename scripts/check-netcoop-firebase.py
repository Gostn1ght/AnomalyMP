"""Negative live probe: validates project/key/provider without creating a user.
No real credentials are accepted or logged. Run explicitly with --live.
"""
import configparser
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path
if '--live' not in sys.argv:
    raise SystemExit('Use --live to make one invalid-credentials request to Google.')
root=Path(__file__).resolve().parents[1]
config=configparser.ConfigParser()
config.read(root/'scripts/netcoop-overlay/client/configs/netcoop/firebase.ltx')
key=config['firebase']['api_key']
request=urllib.request.Request(
    'https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key='+key,
    data=json.dumps({'email':'netcoop-negative-probe@example.invalid', 'password':'not-a-real-user-password', 'returnSecureToken':True}).encode(),
    headers={'Content-Type':'application/json'})
try:
    with urllib.request.urlopen(request,timeout=25) as response:
        response.read()
    raise SystemExit('Unexpected sign-in success for reserved invalid email.')
except urllib.error.HTTPError as error:
    payload=json.loads(error.read())
    code=payload.get('error',{}).get('message','UNKNOWN')
    print('Firebase negative sign-in:',code)
    if code not in ('INVALID_LOGIN_CREDENTIALS','EMAIL_NOT_FOUND','INVALID_PASSWORD'):
        raise SystemExit(1)
print('HTTPS API key and Email/Password provider PASS; no account created, no email sent.')
