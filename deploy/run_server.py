"""Container entry point; live collection requires an explicit opt-in."""

import os

from krisha_list.cli import main


live = os.environ.get("KRISHA_ENABLE_LIVE", "0")
if live not in {"0", "1"}:
    raise SystemExit("KRISHA_ENABLE_LIVE must be 0 or 1")

host_port = os.environ.get("KRISHA_HOST_PORT", "8765")
if not host_port.isdecimal() or not 1 <= int(host_port) <= 65535:
    raise SystemExit("KRISHA_HOST_PORT must be a valid port")
arguments = ["serve", "--host", "0.0.0.0", "--port", "8765", "--db", "/app/data/krisha.sqlite3",
             "--ui-origin", f"http://127.0.0.1:{host_port}"]
if live == "1":
    arguments.append("--enable-live")
raise SystemExit(main(arguments))
