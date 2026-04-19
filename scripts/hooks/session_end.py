import json
from pathlib import Path
import sys


def main() -> None:
    payload = json.load(sys.stdin)
    project_root = Path(__file__).resolve().parents[2]
    audit_path = project_root / "storage" / ".hook-audit.jsonl"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "event": payload.get("hook_event_name"),
                    "session_id": payload.get("session_id"),
                    "cwd": payload.get("cwd"),
                }
            )
            + "\n"
        )


if __name__ == "__main__":
    main()
