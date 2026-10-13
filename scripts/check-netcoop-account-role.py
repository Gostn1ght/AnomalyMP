"""Admin Rights.cmd -> hoster/netcoop_account_role.ps1 on a stand-in accounts
file (owner 2026-10-10: how to give admin on the server). Only the role (and,
for admin, the approval) of that login changes; every other byte stays; the
servers' lock is released; an unknown login changes nothing. Nothing starts."""
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess

root = Path(__file__).resolve().parents[1]
script = root / 'scripts/netcoop-cluster/netcoop_account_role.ps1'
header = '# NetAnomaly accounts: login|role|salt|pbkdf2-sha256|money|device-digest|approval\n'
rows = ['Stalker_1|player|aa|bb|1500|dd|pending|uid1\n', 'other.one|player|cc|ee|-|ff|approved|\n', 'Old-Acc|admin|11|22\n']

def run(runtime, *args):
    return subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script), '-Runtime', str(runtime)] + list(args),
                          capture_output=True, text=True)

with TemporaryDirectory() as temp:
    runtime = Path(temp) / 'Lost Zone'
    data = runtime / 'appdata/server'; data.mkdir(parents=True)
    accounts = data / 'netcoop_accounts.txt'
    accounts.write_bytes((header + ''.join(rows)).encode('ascii'))
    listed = run(runtime, '-List')
    assert listed.returncode == 0 and '3 account(s)' in listed.stdout and 'Stalker_1' in listed.stdout, listed
    granted = run(runtime, '-Login', 'stalker_1', '-Role', 'admin')
    assert granted.returncode == 0 and 'is now admin' in granted.stdout, granted
    text = accounts.read_text(encoding='ascii')
    assert text == header + 'Stalker_1|admin|aa|bb|1500|dd|approved|uid1\n' + rows[1] + rows[2], text
    assert not (data / 'netcoop_locks/accounts.lock').exists()
    assert not list(data.glob('*.tmp'))
    # Approving ordinary players must not grant the admin role or rewrite
    # credentials, device binding, balance, Firebase UID or another account.
    accounts.write_bytes((header + ''.join(rows)).encode('ascii'))
    approved = run(runtime, '-Login', 'STALKER_1', '-Approve')
    assert approved.returncode == 0 and 'registration approved' in approved.stdout, approved
    expected = header + rows[0].replace('|pending|', '|approved|') + rows[1] + rows[2]
    assert accounts.read_text(encoding='ascii') == expected
    repeated = run(runtime, '-Login', 'Stalker_1', '-Approve')
    assert repeated.returncode == 0 and accounts.read_text(encoding='ascii') == expected
    revoked = run(runtime, '-Login', 'Old-Acc', '-Role', 'player')
    assert revoked.returncode == 0
    assert accounts.read_text(encoding='ascii').endswith('Old-Acc|player|11|22\n')
    before = accounts.read_bytes()
    missing = run(runtime, '-Login', 'nobody', '-Role', 'admin')
    assert missing.returncode != 0 and accounts.read_bytes() == before
    bad = run(runtime, '-Login', 'x|y', '-Role', 'admin')
    assert bad.returncode != 0 and accounts.read_bytes() == before
    missing = run(runtime, '-Login', 'nobody', '-Approve')
    assert missing.returncode != 0 and accounts.read_bytes() == before
cmd = (root / 'scripts/dist/Admin Rights.cmd').read_text(encoding='ascii')
assert 'netcoop_account_role.ps1' in cmd and '-List' in cmd
approve_cmd = (root / 'scripts/dist/Approve Registration.cmd').read_text(encoding='ascii')
assert '-Approve' in approve_cmd and '-Role admin' not in approve_cmd
print('PASS account moderation: admin bootstrap, role-preserving approval/retry, unknown/invalid login rejected, lock released; nothing started')
