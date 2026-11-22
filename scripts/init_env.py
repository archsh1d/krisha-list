"""Create a local Compose configuration without printing or overwriting the token."""

from pathlib import Path
import os
import secrets


def main() -> None:
    target = Path(__file__).resolve().parents[1] / ".env"
    content = f"KRISHA_API_TOKEN={secrets.token_urlsafe(48)}\nKRISHA_ENABLE_LIVE=0\n"
    try:
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print(f"Already exists: {target}. Token was not changed.")
        return
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(content)
    print(f"Created {target}. Keep this file private.")


if __name__ == "__main__":
    main()
