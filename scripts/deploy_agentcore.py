#!/usr/bin/env python3
"""Small helper for preparing and deploying this project to AgentCore."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

from config.deployment import (
    deploy_bucket_tags,
    build_render_values,
    normalize_bucket_region,
    require_env,
    render_policy_template,
    render_template,
    resolve_account_id,
    resolve_agentcore,
    resolve_execution_role_name,
    resolve_memory_mode,
    run,
)

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


def render_outputs() -> tuple[str, str]:
    values = build_render_values(ROOT)
    dockerfile = render_template(DOCKERFILE_TEMPLATE.read_text(encoding="utf-8"), values)
    agentcore_yaml = render_template(AGENTCORE_TEMPLATE.read_text(encoding="utf-8"), values)
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
    if os.getenv("AGENTCORE_EXECUTION_ROLE_ARN", "").strip():
        return

    values = build_render_values(ROOT)
    trust_policy = render_policy_template(TRUST_POLICY_TEMPLATE, values)
    permissions_policy = render_policy_template(
        PERMISSIONS_POLICY_TEMPLATE,
        values,
        OPTIONAL_S3_WRITE_POLICY_TEMPLATE,
    )

    iam = boto3.client("iam")
    role_name = resolve_execution_role_name()
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
    account_id = resolve_account_id(ROOT)
    region = require_env("AWS_REGION")
    s3 = boto3.client("s3", region_name=region)

    try:
        s3.head_bucket(Bucket=bucket_name, ExpectedBucketOwner=account_id)
        location = s3.get_bucket_location(
            Bucket=bucket_name,
            ExpectedBucketOwner=account_id,
        )
        bucket_region = normalize_bucket_region(location.get("LocationConstraint"))
        if bucket_region != region:
            raise SystemExit(
                f"{purpose} {bucket_name} exists in {bucket_region}, expected {region}."
            )
        print(f"Using existing {purpose}: {bucket_name}")
        return
    except ClientError as exc:
        error = exc.response.get("Error", {})
        code = error.get("Code", "")
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        bucket_region = exc.response.get("ResponseMetadata", {}).get("HTTPHeaders", {}).get(
            "x-amz-bucket-region"
        )
        if code in {"404", "NoSuchBucket", "NotFound"} or status == 404:
            pass
        elif code in {"301", "PermanentRedirect"} or status == 301:
            raise SystemExit(
                f"{purpose} {bucket_name} exists in {bucket_region or 'another region'}, expected {region}."
            ) from exc
        elif code in {"403", "AccessDenied"} or status == 403:
            raise SystemExit(
                f"{purpose} {bucket_name} exists but is not accessible in account {account_id}."
            ) from exc
        else:
            raise

    tags = deploy_bucket_tags()
    create_args: dict[str, object] = {"Bucket": bucket_name}
    if region != "us-east-1":
        create_args["CreateBucketConfiguration"] = {"LocationConstraint": region}

    try:
        s3.create_bucket(**create_args)
        s3.put_bucket_tagging(Bucket=bucket_name, Tagging={"TagSet": tags})
    except ClientError as exc:
        raise SystemExit(
            f"Failed to create {purpose} {bucket_name}. "
            "Check bucket-tag permissions and org tag policies."
        ) from exc
    print(f"Created {purpose}: {bucket_name}")


def ensure_codebuild_source_bucket() -> None:
    values = build_render_values(ROOT)
    ensure_bucket(values["CODEBUILD_SOURCE_BUCKET"], "deployment bucket")


def check() -> None:
    print(f"Deployment templates: {TEMPLATE_DIR}")
    print(f"AWS region: {require_env('AWS_REGION')}")
    print(f"AgentCore CLI: {resolve_agentcore(ROOT)}")
    docker_bin = shutil.which("docker")
    if not docker_bin:
        raise SystemExit("Docker is required but was not found.")
    print(f"Docker: {docker_bin}")
    values = build_render_values(ROOT)
    print(f"AWS account: {values['AWS_ACCOUNT_ID']}")
    print(f"Execution role: {values['EXECUTION_ROLE_ARN']}")
    print(f"Deployment bucket: {values['CODEBUILD_SOURCE_BUCKET']}")
    print(f"AgentCore memory mode: {resolve_memory_mode()}")
    print("Deployment templates are ready to be written with `prepare` or `deploy`.")


def write_deploy_files() -> tuple[Path, Path]:
    dockerfile_text, agentcore_yaml_text = render_outputs()
    dockerfile_path = ROOT / "Dockerfile"
    agentcore_path = ROOT / ".bedrock_agentcore.yaml"

    dockerfile_path.write_text(dockerfile_text, encoding="utf-8")
    agentcore_path.write_text(agentcore_yaml_text, encoding="utf-8")
    return dockerfile_path, agentcore_path


def deploy() -> None:
    ensure_execution_role()
    ensure_codebuild_source_bucket()
    write_deploy_files()
    code = run([resolve_agentcore(ROOT), "deploy", "--auto-update-on-conflict"], ROOT)
    raise SystemExit(code)


def status() -> None:
    code = run([resolve_agentcore(ROOT), "status"], ROOT)
    raise SystemExit(code)


def invoke(query: str, agent_name: str | None) -> None:
    payload = json.dumps({"query": query})
    cmd = [resolve_agentcore(ROOT), "invoke"]
    if agent_name:
        cmd.extend(["--agent", agent_name])
    cmd.append(payload)
    code = run(cmd, ROOT)
    raise SystemExit(code)


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
    parser = build_parser()
    args = parser.parse_args()

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
