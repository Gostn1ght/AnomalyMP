"""Exercise shipped CMD launchers without starting a game or world master."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
for source in (ROOT / "scripts/dist").glob("*.cmd"):
    data = source.read_bytes()
    assert not data.startswith(b"\xef\xbb\xbf"), f"CMD does not accept UTF-8 BOM: {source.name}"
    assert b"\n" in data and b"\n" not in data.replace(b"\r\n", b""), f"CMD requires CRLF: {source.name}"

if os.name == "nt":
    with tempfile.TemporaryDirectory(prefix="lost zone batch ") as directory:
        folder = Path(directory)
        batch = folder / "Start Locations.cmd"
        shutil.copyfile(ROOT / "scripts/dist" / batch.name, batch)

        def launch():
            # Empty stdin makes pause return. The incomplete test folder is
            # deliberate: either missing executable or missing Python stops
            # BEFORE the batch can start a real native process or master.
            result = subprocess.run(["cmd.exe", "/d", "/c", str(batch)],
                                    input=b"", capture_output=True, timeout=45)
            assert result.returncode == 1, (result.returncode, result.stderr)
            assert not result.stderr, result.stderr
            return result.stdout.decode("utf-8", errors="strict")

        output = launch()
        assert "Не найден dedicated\\LostZoneServerDX11.exe" in output
        assert not (folder / "appdata").exists()

        # Reach the actual Windows PowerShell master preflight, without its
        # Python runtime. An empty executable is only an existence sentinel:
        # it MUST never be executed, since the master failure exits first.
        (folder / "dedicated").mkdir()
        (folder / "dedicated/LostZoneServerDX11.exe").touch()
        (folder / "hoster").mkdir()
        for name in ("netcoop_master_control.ps1", "netcoop_cluster.ltx.six"):
            shutil.copyfile(ROOT / "scripts/netcoop-cluster" / name, folder / "hoster" / name)
        shutil.copyfile(ROOT / "scripts/dist/fsgame_server.template", folder / "fsgame_server.template")
        output = launch()
        assert "Мастер мира не запустился" in output
        log = folder / "appdata/server/logs/start_locations.log"
        assert log.is_file() and log.stat().st_size
        assert (folder / "fsgame_server.ltx").is_file()
        assert not (folder / "hoster/master").exists()
        print("PASS actual Windows CMD: readable missing-exe error, master failure logged, paths with spaces, no game/master launched")

print("PASS distributable CMD launchers: CRLF, no UTF-8 BOM")
