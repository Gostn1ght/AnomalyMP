"""Set the archive build secret using GH's token, never logging that token/key.
Run once by the owner; reruns keep the existing local key to retain patch compatibility.
"""
from pathlib import Path
import argparse
import base64
import json
import secrets
import subprocess
from nacl.public import PublicKey, SealedBox

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--key',required=True);parser.add_argument('--api-ip',required=True)
    args=parser.parse_args();path=Path(args.key);path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists():
        with path.open('xb') as out: out.write(secrets.token_bytes(32))
    key=path.read_bytes()
    if len(key)!=32:raise ValueError('Invalid existing archive key')
    token=subprocess.run(['gh','auth','token','--hostname','github.com'],capture_output=True,check=True).stdout.decode().strip()
    if not token or any(c in token for c in '\r\n"'):raise ValueError('Invalid authentication token')
    prefix=['curl.exe','--silent','--show-error','--fail','--connect-timeout','15','--resolve',f'api.github.com:443:{args.api_ip}','--config','-']
    base='https://api.github.com/repos/Gostn1ght/AnomalyMP/actions/secrets/'
    auth=f'header = "Authorization: Bearer {token}"\n'
    response=subprocess.run(prefix+[base+'public-key'],input=auth.encode(),capture_output=True,check=True)
    public=json.loads(response.stdout)
    encrypted=SealedBox(PublicKey(base64.b64decode(public['key']))).encrypt(key.hex().encode())
    body=json.dumps({'key_id':public['key_id'],'encrypted_value':base64.b64encode(encrypted).decode()})
    # Config stdin supplies both authorization and the encrypted body, no sensitive argv.
    config=auth+'header = "Content-Type: application/json"\nrequest = "PUT"\ndata = '+json.dumps(body)+'\n'
    response=subprocess.run(prefix+[base+'LZPACK_KEY_V1'],input=config.encode(),capture_output=True,check=True)
    print('LZPACK_KEY_V1 set; local key retained for future patch releases')
if __name__=='__main__':main()
