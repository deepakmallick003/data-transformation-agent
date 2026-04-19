import json
import sys


def main() -> None:
    payload = json.load(sys.stdin)
    session_id = payload.get("session_id", "unknown")
    print(
        "\n".join(
            [
                f"SessionStart hook: active Claude session is {session_id}.",
                "Use the session MCP tools to keep transformation-understanding.md, data-dependency-map.md, and delivery-implementation-plan.md current.",
                "Prefer writing generated deliverables into the active session outputs folder.",
            ]
        )
    )


if __name__ == "__main__":
    main()
