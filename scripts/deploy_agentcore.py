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

DEFAULT_AGENT_NAME = "hmrc-data-transformation-agent"
FALLBACK_AGENT_NAME = "agentcore_agent"
DEFAULT_EXECUTION_ROLE_NAME = "AgentCoreRuntimeExecutionRole"
OPTIONAL_ENV_KEYS = [
    "AGENT_TOOLS",
    "ATHENA_DATABASE",
    "ATHENA_OUTPUT_LOCATION",
    "DEFAULT_STORAGE_MODE",
    "KNOWLEDGE_BASE_ID",
    "KB_MAX_RESULTS",
    "S3_READ_BUCKET",
    "S3_READ_PREFIX",
    "S3_WRITE_BUCKET",
    "S3_WRITE_PREFIX",
    "S3_MAX_LIST_RESULTS",
    "S3_MAX_OBJECT_BYTES",
]
BUCKET_TAG_KEYS = [
    "AWS_TAG_CREATEDBY",
    "AWS_TAG_PURPOSE",
    "AWS_TAG_PROJECT",
    "AWS_TAG_ENVIRONMENT",
    "AWS_TAG_OWNER",
    "AWS_TAG_EXPIRYDATE",
]
BUCKET_TAG_NAMES = {
    "AWS_TAG_CREATEDBY": "CreatedBy",
    "AWS_TAG_PURPOSE": "Purpose",
    "AWS_TAG_PROJECT": "Project",
    "AWS_TAG_ENVIRONMENT": "Environment",
    "AWS_TAG_OWNER": "Owner",
    "AWS_TAG_EXPIRYDATE": "ExpiryDate",
}

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
TEMPLATE_DIR = ROOT / "config" / "templates" / "agentcore"
DOCKERFILE_TEMPLATE = TEMPLATE_DIR / "Dockerfile.template"
AGENTCORE_TEMPLATE = TEMPLATE_DIR / "bedrock_agentcore.yaml.template"
TRUST_POLICY_TEMPLATE = TEMPLATE_DIR / "agentcore-execution-trust-policy.template.json"
PERMISSIONS_POLICY_TEMPLATE = TEMPLATE_DIR / "agentcore-execution-permissions.template.json"
OPTIONAL_S3_WRITE_POLICY_TEMPLATE = (
    TEMPLATE_DIR / "agentcore-execution-permissions.s3-write-block.template.json"
)


def load_env() -> None:
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=True)


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def required_env(name: str) -> str:
    value = env(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def agent_name() -> str:
    raw_name = env("AGENTCORE_AGENT_NAME", DEFAULT_AGENT_NAME)
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in raw_name.strip())
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    cleaned = cleaned.strip("_").lower()
    return cleaned[:47] or FALLBACK_AGENT_NAME


def execution_role_name() -> str:
    return env("AGENTCORE_EXECUTION_ROLE_NAME", DEFAULT_EXECUTION_ROLE_NAME)


def run(cmd: list[str]) -> int:
    env_vars = os.environ.copy()
    env_vars.setdefault("PYTHONUNBUFFERED", "1")
    return subprocess.run(cmd, cwd=str(ROOT), env=env_vars).returncode


def run_capture(cmd: list[str]) -> str:
    env_vars = os.environ.copy()
    env_vars.setdefault("PYTHONUNBUFFERED", "1")
    result = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=env_vars,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def agentcore_bin() -> str:
    local = ROOT / ".venv" / "bin" / "agentcore"
    if local.exists():
        return str(local)
    found = shutil.which("agentcore")
    if found:
        return found
    raise SystemExit("Could not find `agentcore`.")


def account_id() -> str:
    value = env("AWS_ACCOUNT_ID")
    if value:
        return value

    role_arn = env("AGENTCORE_EXECUTION_ROLE_ARN")
    if role_arn:
        parts = role_arn.split(":")
        if len(parts) >= 5 and parts[4]:
            return parts[4]

    return run_capture(
        ["aws", "sts", "get-caller-identity", "--query", "Account", "--output", "text"]
    )


def role_arn(aws_account_id: str) -> str:
    explicit = env("AGENTCORE_EXECUTION_ROLE_ARN")
    if explicit:
        return explicit
    return f"arn:aws:iam::{aws_account_id}:role/{execution_role_name()}"


def platform_name() -> str:
    machine = platform.machine().lower()
    return "linux/arm64" if machine in {"arm64", "aarch64"} else "linux/amd64"


def memory_mode() -> str:
    mode = env("AGENTCORE_MEMORY_MODE", "STM_ONLY").upper()
    valid_modes = {"NO_MEMORY", "STM_ONLY", "STM_AND_LTM"}
    if mode not in valid_modes:
        raise SystemExit(
            "AGENTCORE_MEMORY_MODE must be one of: " + ", ".join(sorted(valid_modes))
        )
    return mode


def codebuild_source_bucket(aws_account_id: str, aws_region: str) -> str:
    return f"bedrock-agentcore-codebuild-sources-{aws_account_id}-{aws_region}"


def bucket_region(location: str | None) -> str:
    if not location:
        return "us-east-1"
    if location == "EU":
        return "eu-west-1"
    return location


def bucket_tags() -> list[dict[str, str]]:
    tags: list[dict[str, str]] = []
    missing: list[str] = []

    for key in BUCKET_TAG_KEYS:
        value = env(key)
        if not value:
            missing.append(key)
        else:
            tags.append({"Key": BUCKET_TAG_NAMES[key], "Value": value})

    if missing:
        raise SystemExit(
            "Missing required environment variables for deployment bucket tagging: "
            + ", ".join(missing)
        )

    return tags


def render(text: str, values: dict[str, str]) -> str:
    for key in sorted(values, key=len, reverse=True):
        text = text.replace(f"__{key}__", values[key])
    return text


def optional_env_block() -> str:
    lines: list[str] = []
    for key in OPTIONAL_ENV_KEYS:
        value = env(key)
        if value:
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'ENV {key}="{escaped}"')
    return "\n".join(lines)


def s3_read_object_path() -> str:
    prefix = env("S3_READ_PREFIX").strip("/")
    return f"{prefix}*" if prefix else "*"


def s3_write_object_path() -> str:
    write_bucket = env("S3_WRITE_BUCKET")
    if not write_bucket:
        return ""
    base_prefix = env("S3_WRITE_PREFIX", "agents").strip("/")
    path_parts = [part for part in [base_prefix, agent_name()] if part]
    return "/".join(path_parts) + "/*"


def template_values() -> dict[str, str]:
    aws_region = required_env("AWS_REGION")
    aws_account_id = account_id()

    return {
        "PYTHON_BASE_IMAGE": env(
            "AGENTCORE_PYTHON_BASE_IMAGE",
            "public.ecr.aws/docker/library/python:3.13-slim",
        ),
        "AWS_REGION": aws_region,
        "ANTHROPIC_MODEL": required_env("ANTHROPIC_MODEL"),
        "ANTHROPIC_SMALL_FAST_MODEL": required_env("ANTHROPIC_SMALL_FAST_MODEL"),
        "OPTIONAL_ENV_BLOCK": optional_env_block(),
        "AGENT_NAME": agent_name(),
        "ENTRYPOINT": env("AGENTCORE_ENTRYPOINT", "main.py"),
        "PLATFORM": platform_name(),
        "EXECUTION_ROLE_ARN": role_arn(aws_account_id),
        "AWS_ACCOUNT_ID": aws_account_id,
        "CODEBUILD_SOURCE_BUCKET": codebuild_source_bucket(aws_account_id, aws_region),
        "S3_READ_BUCKET": env("S3_READ_BUCKET", "YOUR_BUCKET_NAME"),
        "S3_READ_PREFIX": env("S3_READ_PREFIX").strip("/"),
        "S3_READ_OBJECT_PATH": s3_read_object_path(),
        "S3_WRITE_BUCKET": env("S3_WRITE_BUCKET"),
        "S3_WRITE_PREFIX": env("S3_WRITE_PREFIX", "agents").strip("/"),
        "S3_WRITE_OBJECT_PATH": s3_write_object_path(),
        "AGENTCORE_MEMORY_MODE": memory_mode(),
    }


def render_policy(
    template_path: Path,
    values: dict[str, str],
    include_optional_s3_write: bool = False,
) -> str:
    policy = json.loads(render(template_path.read_text(encoding="utf-8"), values))

    if include_optional_s3_write and values["S3_WRITE_BUCKET"]:
        extra_statements = json.loads(
            render(
                OPTIONAL_S3_WRITE_POLICY_TEMPLATE.read_text(encoding="utf-8"),
                values,
            )
        )
        policy["Statement"].extend(extra_statements)

    return json.dumps(policy)


def render_outputs() -> tuple[str, str]:
    values = template_values()
    dockerfile = render(DOCKERFILE_TEMPLATE.read_text(encoding="utf-8"), values)
    agentcore_yaml = render(AGENTCORE_TEMPLATE.read_text(encoding="utf-8"), values)
    return dockerfile, agentcore_yaml


def prepare() -> None:
    dockerfile_text, agentcore_yaml_text = render_outputs()
    dockerfile_path = ROOT / "Dockerfile"
    agentcore_path = ROOT / ".bedrock_agentcore.yaml"
    dockerfile_path.write_text(dockerfile_text, encoding="utf-8")
    agentcore_path.write_text(agentcore_yaml_text, encoding="utf-8")
    print(f"Wrote {dockerfile_path}")
    print(f"Wrote {agentcore_path}")


def ensure_execution_role() -> None:
    if env("AGENTCORE_EXECUTION_ROLE_ARN"):
        return

    values = template_values()
    trust_policy = render_policy(TRUST_POLICY_TEMPLATE, values)
    permissions_policy = render_policy(
        PERMISSIONS_POLICY_TEMPLATE,
        values,
        include_optional_s3_write=True,
    )

    iam = boto3.client("iam")
    role_name = execution_role_name()
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


def ensure_bucket(bucket_name: str, purpose: str) -> None:
    aws_account_id = account_id()
    aws_region = required_env("AWS_REGION")
    s3 = boto3.client("s3", region_name=aws_region)

    try:
        s3.head_bucket(Bucket=bucket_name, ExpectedBucketOwner=aws_account_id)
        location = s3.get_bucket_location(
            Bucket=bucket_name,
            ExpectedBucketOwner=aws_account_id,
        )
        current_region = bucket_region(location.get("LocationConstraint"))
        if current_region != aws_region:
            raise SystemExit(
                f"{purpose} {bucket_name} exists in {current_region}, expected {aws_region}."
            )
        print(f"Using existing {purpose}: {bucket_name}")
        return
    except ClientError as exc:
        error = exc.response.get("Error", {})
        code = error.get("Code", "")
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        current_region = exc.response.get("ResponseMetadata", {}).get("HTTPHeaders", {}).get(
            "x-amz-bucket-region"
        )
        if code in {"404", "NoSuchBucket", "NotFound"} or status == 404:
            pass
        elif code in {"301", "PermanentRedirect"} or status == 301:
            raise SystemExit(
                f"{purpose} {bucket_name} exists in {current_region or 'another region'}, "
                f"expected {aws_region}."
            ) from exc
        elif code in {"403", "AccessDenied"} or status == 403:
            raise SystemExit(
                f"{purpose} {bucket_name} exists but is not accessible in account "
                f"{aws_account_id}."
            ) from exc
        else:
            raise

    create_args: dict[str, object] = {"Bucket": bucket_name}
    if aws_region != "us-east-1":
        create_args["CreateBucketConfiguration"] = {"LocationConstraint": aws_region}

    try:
        s3.create_bucket(**create_args)
        s3.put_bucket_tagging(Bucket=bucket_name, Tagging={"TagSet": bucket_tags()})
    except ClientError as exc:
        raise SystemExit(
            f"Failed to create {purpose} {bucket_name}. "
            "Check bucket-tag permissions and org tag policies."
        ) from exc

    print(f"Created {purpose}: {bucket_name}")


def ensure_codebuild_source_bucket() -> None:
    values = template_values()
    ensure_bucket(values["CODEBUILD_SOURCE_BUCKET"], "deployment bucket")


def check() -> None:
    values = template_values()
    print(f"Deployment templates: {TEMPLATE_DIR}")
    print(f"AWS region: {required_env('AWS_REGION')}")
    print(f"AgentCore CLI: {agentcore_bin()}")

    docker_bin = shutil.which("docker")
    if not docker_bin:
        raise SystemExit("Docker is required but was not found.")

    print(f"Docker: {docker_bin}")
    print(f"AWS account: {values['AWS_ACCOUNT_ID']}")
    print(f"Execution role: {values['EXECUTION_ROLE_ARN']}")
    print(f"Deployment bucket: {values['CODEBUILD_SOURCE_BUCKET']}")
    print(f"AgentCore memory mode: {memory_mode()}")
    print("Deployment templates are ready to be written with `prepare` or `deploy`.")


def deploy() -> None:
    ensure_execution_role()
    ensure_codebuild_source_bucket()
    prepare()
    raise SystemExit(run([agentcore_bin(), "deploy", "--auto-update-on-conflict"]))


def status() -> None:
    raise SystemExit(run([agentcore_bin(), "status"]))


def invoke(query: str, chosen_agent: str | None) -> None:
    payload = json.dumps({"query": query})
    cmd = [agentcore_bin(), "invoke"]
    if chosen_agent:
        cmd.extend(["--agent", chosen_agent])
    cmd.append(payload)
    raise SystemExit(run(cmd))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deploy this project to AgentCore.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    sub.add_parser("prepare")
    sub.add_parser("deploy")
    sub.add_parser("status")
    invoke_parser = sub.add_parser("invoke")
    invoke_parser.add_argument("query")
    invoke_parser.add_argument("--agent", default=None)
    return parser


def main() -> None:
    load_env()
    args = build_parser().parse_args()

    if args.command == "check":
        check()
    elif args.command == "prepare":
        prepare()
    elif args.command == "deploy":
        deploy()
    elif args.command == "status":
        status()
    elif args.command == "invoke":
        invoke(args.query, args.agent)


if __name__ == "__main__":
    main()
