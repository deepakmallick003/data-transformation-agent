#!/usr/bin/env python3
"""Small helper for preparing and deploying this project to AgentCore."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
DEPLOY_DIR = ROOT / "config" / "agentcore"
DOCKERFILE_TEMPLATE = DEPLOY_DIR / "Dockerfile.template"
AGENTCORE_TEMPLATE = DEPLOY_DIR / "bedrock_agentcore.yaml.template"
TRUST_POLICY_TEMPLATE = DEPLOY_DIR / "agentcore-execution-trust-policy.template.json"
PERMISSIONS_POLICY_TEMPLATE = DEPLOY_DIR / "agentcore-execution-permissions.template.json"

OPTIONAL_ENV_KEYS = [
    "AGENT_TOOLS",
    "ATHENA_DATABASE",
    "ATHENA_OUTPUT_LOCATION",
    "KNOWLEDGE_BASE_ID",
    "KB_MAX_RESULTS",
    "S3_BUCKET",
    "S3_KEY_PREFIX",
    "S3_MAX_LIST_RESULTS",
    "S3_MAX_OBJECT_BYTES",
]


def load_env() -> None:
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=True)


def sanitize_name(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value.strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned.lower() or "agentcore_agent"


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def run(cmd: list[str]) -> int:
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    return subprocess.run(cmd, cwd=str(ROOT), env=env).returncode


def run_capture(cmd: list[str]) -> str:
    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    result = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def resolve_agentcore() -> str:
    local = ROOT / ".venv" / "bin" / "agentcore"
    if local.exists():
        return str(local)
    found = shutil.which("agentcore")
    if found:
        return found
    raise SystemExit("Could not find `agentcore`.")


def resolve_account_id() -> str:
    account_id = os.getenv("AWS_ACCOUNT_ID", "").strip()
    if account_id:
        return account_id
    role_arn = os.getenv("AGENTCORE_EXECUTION_ROLE_ARN", "").strip()
    if role_arn:
        parts = role_arn.split(":")
        if len(parts) >= 5 and parts[4]:
            return parts[4]
    return run_capture(["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"])


def resolve_role_arn() -> str:
    explicit = os.getenv("AGENTCORE_EXECUTION_ROLE_ARN", "").strip()
    if explicit:
        return explicit
    role_name = resolve_role_name()
    return f"arn:aws:iam::{resolve_account_id()}:role/{role_name}"


def resolve_role_name() -> str:
    role_name = os.getenv("AGENTCORE_EXECUTION_ROLE_NAME", "").strip()
    if role_name:
        return role_name
    return "AgentCoreRuntimeExecutionRole"


def resolve_platform() -> str:
    machine = platform.machine().lower()
    return "linux/arm64" if machine in {"arm64", "aarch64"} else "linux/amd64"


def render(text: str, values: dict[str, str]) -> str:
    for key in sorted(values, key=len, reverse=True):
        value = values[key]
        text = text.replace(f"__{key}__", value)
    return text


def optional_env_block() -> str:
    lines: list[str] = []
    for key in OPTIONAL_ENV_KEYS:
        value = os.getenv(key, "").strip()
        if value:
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'ENV {key}="{escaped}"')
    return "\n".join(lines)


def build_render_values() -> dict[str, str]:
    agent_name = sanitize_name(os.getenv("AGENTCORE_AGENT_NAME", ROOT.name))
    account_id = resolve_account_id()
    aws_region = require_env("AWS_REGION")
    return {
        "PYTHON_BASE_IMAGE": os.getenv(
            "AGENTCORE_PYTHON_BASE_IMAGE",
            "public.ecr.aws/docker/library/python:3.13-slim",
        ),
        "AWS_REGION": aws_region,
        "ANTHROPIC_MODEL": require_env("ANTHROPIC_MODEL"),
        "ANTHROPIC_SMALL_FAST_MODEL": require_env("ANTHROPIC_SMALL_FAST_MODEL"),
        "OPTIONAL_ENV_BLOCK": optional_env_block(),
        "AGENT_NAME": agent_name,
        "ENTRYPOINT": os.getenv("AGENTCORE_ENTRYPOINT", "main.py"),
        "PLATFORM": resolve_platform(),
        "EXECUTION_ROLE_ARN": resolve_role_arn(),
        "AWS_ACCOUNT_ID": account_id,
        "S3_BUCKET": os.getenv("S3_BUCKET", "YOUR_BUCKET_NAME").strip() or "YOUR_BUCKET_NAME",
    }


def render_outputs() -> tuple[str, str]:
    values = build_render_values()
    dockerfile = render(DOCKERFILE_TEMPLATE.read_text(encoding="utf-8"), values)
    agentcore_yaml = render(AGENTCORE_TEMPLATE.read_text(encoding="utf-8"), values)
    return dockerfile, agentcore_yaml


def prepare() -> None:
    render_outputs()
    print("Deployment templates rendered successfully.")
    print("`deploy` will use temporary deployment config only for the AgentCore CLI run and will not leave generated files behind.")


def ensure_execution_role() -> None:
    if os.getenv("AGENTCORE_EXECUTION_ROLE_ARN", "").strip():
        return

    values = build_render_values()
    trust_policy = render(TRUST_POLICY_TEMPLATE.read_text(encoding="utf-8"), values)
    permissions_policy = render(
        PERMISSIONS_POLICY_TEMPLATE.read_text(encoding="utf-8"), values
    )

    iam = boto3.client("iam")
    role_name = resolve_role_name()
    policy_name = f"{role_name}Policy"

    try:
        iam.get_role(RoleName=role_name)
        iam.update_assume_role_policy(
            RoleName=role_name,
            PolicyDocument=trust_policy,
        )
        print(f"Updated IAM role trust policy: {role_name}")
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code != "NoSuchEntity":
            raise
        iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=trust_policy,
            Description="AgentCore runtime execution role",
        )
        print(f"Created IAM role: {role_name}")

    iam.put_role_policy(
        RoleName=role_name,
        PolicyName=policy_name,
        PolicyDocument=permissions_policy,
    )
    print(f"Applied inline IAM policy: {policy_name}")


def check() -> None:
    print(f"Deployment config: {DEPLOY_DIR}")
    print(f"AWS region: {require_env('AWS_REGION')}")
    print(f"AgentCore CLI: {resolve_agentcore()}")
    docker_bin = shutil.which("docker")
    if not docker_bin:
        raise SystemExit("Docker is required but was not found.")
    print(f"Docker: {docker_bin}")
    print(f"AWS account: {resolve_account_id()}")
    print(f"Execution role: {resolve_role_arn()}")
    render_outputs()
    print("Deployment templates render successfully.")


def write_deploy_files() -> tuple[Path, Path]:
    dockerfile_text, agentcore_yaml_text = render_outputs()
    dockerfile_path = ROOT / "Dockerfile"
    agentcore_path = ROOT / ".bedrock_agentcore.yaml"

    dockerfile_path.write_text(dockerfile_text, encoding="utf-8")
    agentcore_path.write_text(agentcore_yaml_text, encoding="utf-8")
    return dockerfile_path, agentcore_path


def deploy(keep_files: bool) -> None:
    ensure_execution_role()
    dockerfile_path, agentcore_path = write_deploy_files()
    try:
        code = run([resolve_agentcore(), "deploy"])
    finally:
        if not keep_files:
            dockerfile_path.unlink(missing_ok=True)
            agentcore_path.unlink(missing_ok=True)
    raise SystemExit(code)


def status() -> None:
    code = run([resolve_agentcore(), "status"])
    raise SystemExit(code)


def invoke(query: str, agent_name: str | None) -> None:
    payload = json.dumps({"query": query})
    cmd = [resolve_agentcore(), "invoke"]
    if agent_name:
        cmd.extend(["--agent", agent_name])
    cmd.append(payload)
    code = run(cmd)
    raise SystemExit(code)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deploy this project to AgentCore.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    sub.add_parser("prepare")
    deploy_parser = sub.add_parser("deploy")
    deploy_parser.add_argument(
        "--keep-files",
        action="store_true",
        help="Keep rendered Dockerfile and .bedrock_agentcore.yaml in the repo root after deploy.",
    )
    sub.add_parser("status")
    invoke_parser = sub.add_parser("invoke")
    invoke_parser.add_argument("query")
    invoke_parser.add_argument("--agent", default=None)
    return parser


def main() -> None:
    load_env()
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "check":
        check()
    elif args.command == "prepare":
        prepare()
    elif args.command == "deploy":
        deploy(args.keep_files)
    elif args.command == "status":
        status()
    elif args.command == "invoke":
        invoke(args.query, args.agent)


if __name__ == "__main__":
    main()
