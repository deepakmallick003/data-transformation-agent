#!/usr/bin/env python3
"""Simple helper to invoke AgentCore from CLI."""

import argparse
import json
import subprocess

from deploy_agentcore import load_env, resolve_agentcore


def main() -> None:
    load_env()
    parser = argparse.ArgumentParser(description="Invoke AgentCore with a JSON query payload")
    parser.add_argument("query", nargs="+", help="User query text")
    parser.add_argument("--dev", action="store_true", help="Use local dev invocation")
    parser.add_argument("--agent", default=None, help="Optional deployed agent name")
    args = parser.parse_args()

    cmd = [resolve_agentcore(), "invoke"]
    if args.dev:
        cmd.append("--dev")
    if args.agent:
        cmd.extend(["--agent", args.agent])

    payload = {"query": " ".join(args.query)}
    cmd.append(json.dumps(payload))

    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
