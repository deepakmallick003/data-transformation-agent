"""Customs declaration PDF to Snowflake transformation bundle.

This script is designed to run from an extracted handoff bundle as well as from the repository.
It fetches batch metadata and PDF documents from S3, extracts declaration content, writes local
staging outputs, and can optionally load curated rows into Snowflake.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable


MRN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{2}[A-Z0-9]{14,18}$")
COMMODITY_CODE_PATTERN = re.compile(r"^[0-9]{8,10}$")

HEADER_FIELDS = [
    "DECLARATION_KEY",
    "MRN",
    "DECLARANT_EORI",
    "DECLARATION_TYPE",
    "SUBMISSION_TIMESTAMP",
    "GOODS_LOCATION_CODE",
    "TOTAL_CUSTOMS_VALUE",
    "SOURCE_DOCUMENT_KEY",
    "LOAD_TIMESTAMP",
]

LINE_FIELDS = [
    "DECLARATION_LINE_KEY",
    "DECLARATION_KEY",
    "LINE_NUMBER",
    "COMMODITY_CODE",
    "ORIGIN_COUNTRY_CODE",
    "PROCEDURE_CODE",
    "NET_MASS_KG",
    "STATISTICAL_VALUE",
    "LOAD_TIMESTAMP",
]

REJECTION_FIELDS = [
    "REJECTION_ID",
    "BATCH_ID",
    "DOCUMENT_KEY",
    "MRN",
    "ERROR_CODE",
    "ERROR_MESSAGE",
    "RAW_CONTEXT",
    "REJECTED_AT",
]


@dataclass
class RejectionRecord:
    rejection_id: int
    batch_id: str
    document_key: str
    mrn: str
    error_code: str
    error_message: str
    raw_context: str
    rejected_at: str

    def as_row(self) -> dict[str, str]:
        return {
            "REJECTION_ID": str(self.rejection_id),
            "BATCH_ID": self.batch_id,
            "DOCUMENT_KEY": self.document_key,
            "MRN": self.mrn,
            "ERROR_CODE": self.error_code,
            "ERROR_MESSAGE": self.error_message,
            "RAW_CONTEXT": self.raw_context,
            "REJECTED_AT": self.rejected_at,
        }


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.strip().split())


def parse_decimal(value: str | None) -> Decimal:
    cleaned = clean(value)
    if not cleaned:
        raise ValueError("Missing decimal value")
    try:
        return Decimal(cleaned.replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal value: {cleaned}") from exc


def parse_iso_timestamp(value: str | None) -> str:
    cleaned = clean(value)
    if not cleaned:
        raise ValueError("Missing submission timestamp")
    normalized = cleaned.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def create_s3_client():
    try:
        import boto3  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "boto3 is required for S3 access. Install it before running this script."
        ) from exc
    region = get_env("AWS_REGION", "eu-west-2")
    return boto3.client("s3", region_name=region)


def create_snowflake_connection():
    try:
        import snowflake.connector  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "snowflake-connector-python is required for Snowflake loads."
        ) from exc

    return snowflake.connector.connect(
        account=get_env("SNOWFLAKE_ACCOUNT"),
        user=get_env("SNOWFLAKE_USER"),
        password=get_env("SNOWFLAKE_PASSWORD"),
        warehouse=get_env("SNOWFLAKE_WAREHOUSE"),
        database=get_env("SNOWFLAKE_DATABASE"),
        schema=get_env("SNOWFLAKE_SCHEMA"),
        role=os.getenv("SNOWFLAKE_ROLE"),
    )


def read_s3_json(client, bucket: str, key: str) -> dict:
    response = client.get_object(Bucket=bucket, Key=key)
    return json.loads(response["Body"].read().decode("utf-8"))


def read_s3_csv(client, bucket: str, key: str, delimiter: str = "|") -> list[dict[str, str]]:
    response = client.get_object(Bucket=bucket, Key=key)
    text = response["Body"].read().decode("utf-8")
    return list(csv.DictReader(io.StringIO(text), delimiter=delimiter))


def read_s3_bytes(client, bucket: str, key: str) -> bytes:
    response = client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


def parse_pdf_text(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "pypdf is required for PDF parsing. Install it before running this script."
        ) from exc

    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_single(pattern: str, text: str, field_name: str) -> str:
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        raise ValueError(f"Missing {field_name} in PDF text")
    return clean(match.group(1))


def extract_lines(text: str) -> list[dict[str, str]]:
    matches = re.findall(
        r"LINE\s+(\d+)\s*\|\s*COMMODITY\s+([0-9]{8,10})\s*\|\s*ORIGIN\s+([A-Z]{2})\s*\|\s*PROCEDURE\s+([A-Z0-9]{4})\s*\|\s*MASS\s+([0-9.,]+)\s*\|\s*VALUE\s+([0-9.,]+)",
        text,
        flags=re.MULTILINE,
    )
    line_rows: list[dict[str, str]] = []
    for line_number, commodity_code, origin, procedure, mass, value in matches:
        line_rows.append(
            {
                "LINE_NUMBER": line_number,
                "COMMODITY_CODE": commodity_code,
                "ORIGIN_COUNTRY_CODE": origin,
                "PROCEDURE_CODE": procedure,
                "NET_MASS_KG": f"{parse_decimal(mass):.3f}",
                "STATISTICAL_VALUE": f"{parse_decimal(value):.2f}",
            }
        )
    return line_rows


def validate_mrn(mrn: str) -> None:
    if not MRN_PATTERN.match(mrn):
        raise ValueError(f"Invalid MRN: {mrn}")


def validate_commodity_code(code: str) -> None:
    if not COMMODITY_CODE_PATTERN.match(code):
        raise ValueError(f"Invalid commodity code: {code}")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def add_rejection(
    rows: list[dict[str, str]],
    next_id: list[int],
    batch_id: str,
    document_key: str,
    mrn: str,
    error_code: str,
    error_message: str,
    raw_context: str,
) -> None:
    next_id[0] += 1
    rows.append(
        RejectionRecord(
            rejection_id=next_id[0],
            batch_id=batch_id,
            document_key=document_key,
            mrn=mrn,
            error_code=error_code,
            error_message=error_message,
            raw_context=raw_context,
            rejected_at=utc_now(),
        ).as_row()
    )


def load_to_snowflake(
    headers: list[dict[str, str]],
    lines: list[dict[str, str]],
    rejections: list[dict[str, str]],
) -> None:
    connection = create_snowflake_connection()
    try:
        cursor = connection.cursor()
        try:
            cursor.executemany(
                """
                INSERT INTO CURATED_CUSTOMS_DECLARATION_HEADER
                (DECLARATION_KEY, MRN, DECLARANT_EORI, DECLARATION_TYPE, SUBMISSION_TIMESTAMP,
                 GOODS_LOCATION_CODE, TOTAL_CUSTOMS_VALUE, SOURCE_DOCUMENT_KEY, LOAD_TIMESTAMP)
                VALUES (%(DECLARATION_KEY)s, %(MRN)s, %(DECLARANT_EORI)s, %(DECLARATION_TYPE)s,
                        %(SUBMISSION_TIMESTAMP)s, %(GOODS_LOCATION_CODE)s, %(TOTAL_CUSTOMS_VALUE)s,
                        %(SOURCE_DOCUMENT_KEY)s, %(LOAD_TIMESTAMP)s)
                """,
                headers,
            )
            cursor.executemany(
                """
                INSERT INTO CURATED_CUSTOMS_DECLARATION_LINE
                (DECLARATION_LINE_KEY, DECLARATION_KEY, LINE_NUMBER, COMMODITY_CODE,
                 ORIGIN_COUNTRY_CODE, PROCEDURE_CODE, NET_MASS_KG, STATISTICAL_VALUE, LOAD_TIMESTAMP)
                VALUES (%(DECLARATION_LINE_KEY)s, %(DECLARATION_KEY)s, %(LINE_NUMBER)s,
                        %(COMMODITY_CODE)s, %(ORIGIN_COUNTRY_CODE)s, %(PROCEDURE_CODE)s,
                        %(NET_MASS_KG)s, %(STATISTICAL_VALUE)s, %(LOAD_TIMESTAMP)s)
                """,
                lines,
            )
            cursor.executemany(
                """
                INSERT INTO CUSTOMS_DECLARATION_REJECTION_LOG
                (REJECTION_ID, BATCH_ID, DOCUMENT_KEY, MRN, ERROR_CODE, ERROR_MESSAGE,
                 RAW_CONTEXT, REJECTED_AT)
                VALUES (%(REJECTION_ID)s, %(BATCH_ID)s, %(DOCUMENT_KEY)s, %(MRN)s, %(ERROR_CODE)s,
                        %(ERROR_MESSAGE)s, %(RAW_CONTEXT)s, %(REJECTED_AT)s)
                """,
                rejections,
            )
            connection.commit()
        finally:
            cursor.close()
    finally:
        connection.close()


def run_transformation(business_date: str, output_dir: Path, load_to_target: bool) -> dict[str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    s3_client = create_s3_client()
    bucket = get_env("SOURCE_S3_BUCKET")
    manifest_template = os.getenv(
        "MANIFEST_KEY_TEMPLATE", "manifests/{yyyy}/{mm}/{dd}/manifest_{yyyymmdd}.json"
    )
    index_template = os.getenv(
        "INDEX_KEY_TEMPLATE", "index/{yyyy}/{mm}/{dd}/declaration_index_{yyyymmdd}.csv"
    )
    yyyy, mm, dd = business_date[:4], business_date[4:6], business_date[6:8]
    template_args = {
        "yyyy": yyyy,
        "mm": mm,
        "dd": dd,
        "yyyymmdd": business_date,
    }
    manifest_key = manifest_template.format(**template_args)
    index_key = index_template.format(**template_args)

    manifest = read_s3_json(s3_client, bucket, manifest_key)
    index_rows = read_s3_csv(s3_client, bucket, index_key)

    batch_id = clean(str(manifest.get("batch_id")))
    expected_keys = set(manifest.get("document_keys", []))
    if len(index_rows) != int(manifest.get("expected_document_count", len(index_rows))):
        # keep this as a rejection log row but continue
        pass

    header_rows: list[dict[str, str]] = []
    line_rows: list[dict[str, str]] = []
    rejection_rows: list[dict[str, str]] = []
    rejection_id = [0]
    next_header_id = 100000
    next_line_id = 500000
    seen_mrns: set[str] = set()

    for index_row in index_rows:
        document_key = clean(index_row.get("DOCUMENT_KEY"))
        mrn = clean(index_row.get("MRN"))
        try:
            if document_key not in expected_keys:
                raise ValueError("Document key is not declared in the manifest")
            validate_mrn(mrn)
            if mrn in seen_mrns:
                raise ValueError("Duplicate MRN within batch")
            pdf_bytes = read_s3_bytes(s3_client, bucket, document_key)
            pdf_text = parse_pdf_text(pdf_bytes)
            goods_location = extract_single(r"GOODS LOCATION\s*:\s*(.+)", pdf_text, "GOODS_LOCATION_CODE")
            total_customs_value = f"{parse_decimal(extract_single(r"TOTAL CUSTOMS VALUE\s*:\s*([0-9,]+\.[0-9]{2})", pdf_text, "TOTAL_CUSTOMS_VALUE")):.2f}"
            parsed_lines = extract_lines(pdf_text)
            if not parsed_lines:
                raise ValueError("No commodity lines parsed from PDF")
            declaration_key = str(next_header_id)
            next_header_id += 1
            header_rows.append(
                {
                    "DECLARATION_KEY": declaration_key,
                    "MRN": mrn,
                    "DECLARANT_EORI": clean(index_row.get("DECLARANT_EORI")),
                    "DECLARATION_TYPE": clean(index_row.get("DECLARATION_TYPE")).upper(),
                    "SUBMISSION_TIMESTAMP": parse_iso_timestamp(index_row.get("SUBMISSION_TIMESTAMP")),
                    "GOODS_LOCATION_CODE": goods_location,
                    "TOTAL_CUSTOMS_VALUE": total_customs_value,
                    "SOURCE_DOCUMENT_KEY": document_key,
                    "LOAD_TIMESTAMP": utc_now(),
                }
            )
            seen_mrns.add(mrn)
            for parsed_line in parsed_lines:
                validate_commodity_code(parsed_line["COMMODITY_CODE"])
                line_rows.append(
                    {
                        "DECLARATION_LINE_KEY": str(next_line_id),
                        "DECLARATION_KEY": declaration_key,
                        "LINE_NUMBER": parsed_line["LINE_NUMBER"],
                        "COMMODITY_CODE": parsed_line["COMMODITY_CODE"],
                        "ORIGIN_COUNTRY_CODE": parsed_line["ORIGIN_COUNTRY_CODE"],
                        "PROCEDURE_CODE": parsed_line["PROCEDURE_CODE"],
                        "NET_MASS_KG": parsed_line["NET_MASS_KG"],
                        "STATISTICAL_VALUE": parsed_line["STATISTICAL_VALUE"],
                        "LOAD_TIMESTAMP": utc_now(),
                    }
                )
                next_line_id += 1
        except Exception as exc:  # noqa: BLE001
            add_rejection(
                rejection_rows,
                rejection_id,
                batch_id=batch_id,
                document_key=document_key,
                mrn=mrn,
                error_code="DOCUMENT_REJECTED",
                error_message=str(exc),
                raw_context=json.dumps(index_row, sort_keys=True),
            )

    write_csv(output_dir / "curated_customs_declaration_header.csv", HEADER_FIELDS, header_rows)
    write_csv(output_dir / "curated_customs_declaration_line.csv", LINE_FIELDS, line_rows)
    write_csv(output_dir / "customs_declaration_rejection_log.csv", REJECTION_FIELDS, rejection_rows)
    summary = {
        "header_rows": len(header_rows),
        "line_rows": len(line_rows),
        "rejections": len(rejection_rows),
    }
    (output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    if load_to_target:
        load_to_snowflake(header_rows, line_rows, rejection_rows)

    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Transform customs declaration PDFs from S3 into Snowflake-ready outputs.")
    parser.add_argument("--business-date", required=True, help="Business date in YYYYMMDD format.")
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory for local staged outputs.")
    parser.add_argument(
        "--load-to-snowflake",
        action="store_true",
        help="If set, load accepted rows and rejections into Snowflake after local output generation.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    summary = run_transformation(
        business_date=args.business_date,
        output_dir=args.output_dir,
        load_to_target=args.load_to_snowflake,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
