"""Oracle PL/SQL to SharePoint curated analytics transformation bundle."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Iterable
import zipfile
import xml.etree.ElementTree as ET


OPEN_CASE_FIELDS = [
    "CASE_ID",
    "TAXPAYER_REF",
    "CASE_TYPE",
    "RISK_BAND",
    "ASSIGNED_OFFICER",
    "OPEN_DATE",
    "CASE_STATUS",
    "AGE_DAYS",
]

WORKLOAD_FIELDS = [
    "OFFICER_ID",
    "TEAM_CODE",
    "OPEN_CASE_COUNT",
    "HIGH_RISK_CASE_COUNT",
    "OVERDUE_CASE_COUNT",
]

UPLOAD_MANIFEST_FIELDS = [
    "FILE_NAME",
    "TARGET_FOLDER",
    "ROW_COUNT",
    "PUBLISHED_AT",
    "STATUS",
]

RISK_BAND_MAP = {
    "LOW": "LOW",
    "MEDIUM": "MEDIUM",
    "HIGH": "HIGH",
    "CRITICAL": "CRITICAL",
}


def get_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.strip().split())


def parse_iso_date(value: str | None) -> date:
    cleaned = clean(value)
    if not cleaned:
        raise ValueError("Missing date value")
    return datetime.strptime(cleaned, "%Y-%m-%d").date()


def parse_non_negative_int(value: object, field_name: str) -> int:
    cleaned = clean("" if value is None else str(value))
    if cleaned == "":
        return 0
    try:
        parsed = int(cleaned)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an integer: {cleaned}") from exc
    if parsed < 0:
        raise ValueError(f"{field_name} must be non-negative: {cleaned}")
    return parsed


def create_oracle_connection():
    try:
        import oracledb  # type: ignore
    except ImportError as exc:
        raise RuntimeError("oracledb is required for Oracle access.") from exc

    return oracledb.connect(
        user=get_env("ORACLE_USER"),
        password=get_env("ORACLE_PASSWORD"),
        dsn=get_env("ORACLE_DSN"),
    )


def fetch_result_sets(business_date: str, region_code: str | None) -> dict[str, list[dict[str, object]]]:
    connection = create_oracle_connection()
    try:
        cursor = connection.cursor()
        try:
            # This is a bounded implementation slice: the package call and cursor handling are
            # intentionally explicit rather than relying on hidden framework wrappers.
            open_case_cursor = connection.cursor()
            workload_cursor = connection.cursor()
            trend_cursor = connection.cursor()
            cursor.callproc(
                "HMRC_COMPLIANCE_ANALYTICS_PKG.EXPORT_CASE_ANALYTICS",
                [
                    business_date,
                    region_code,
                    open_case_cursor,
                    workload_cursor,
                    trend_cursor,
                ],
            )
            return {
                "OPEN_CASE_DETAIL": rows_from_cursor(open_case_cursor),
                "OFFICER_WORKLOAD_SUMMARY": rows_from_cursor(workload_cursor),
                "RISK_TREND_SUMMARY": rows_from_cursor(trend_cursor),
            }
        finally:
            cursor.close()
    finally:
        connection.close()


def rows_from_cursor(cursor) -> list[dict[str, object]]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]


def normalize_open_cases(rows: Iterable[dict[str, object]], business_date: date) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen_case_ids: set[str] = set()
    for row in rows:
        case_id = clean(str(row.get("CASE_ID", "")))
        if not case_id:
            raise ValueError("Missing CASE_ID in OPEN_CASE_DETAIL result set")
        if case_id in seen_case_ids:
            raise ValueError(f"Duplicate CASE_ID encountered: {case_id}")
        open_date = parse_iso_date(str(row.get("OPEN_DATE", "")))
        if open_date > business_date:
            raise ValueError(f"OPEN_DATE is in the future for case {case_id}")
        risk_band = clean(str(row.get("RISK_SCORE_BAND", ""))).upper()
        if risk_band not in RISK_BAND_MAP:
            raise ValueError(f"Invalid risk band for case {case_id}: {risk_band}")
        seen_case_ids.add(case_id)
        normalized.append(
            {
                "CASE_ID": case_id,
                "TAXPAYER_REF": clean(str(row.get("TAXPAYER_REF", ""))),
                "CASE_TYPE": clean(str(row.get("CASE_TYPE", ""))).upper(),
                "RISK_BAND": RISK_BAND_MAP[risk_band],
                "ASSIGNED_OFFICER": clean(str(row.get("OFFICER_LOGIN", ""))),
                "OPEN_DATE": open_date.isoformat(),
                "CASE_STATUS": clean(str(row.get("CASE_STATUS", ""))).upper(),
                "AGE_DAYS": str((business_date - open_date).days),
            }
        )
    return normalized


def normalize_workload(rows: Iterable[dict[str, object]]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for row in rows:
        counts = {
            "OPEN_CASE_COUNT": parse_non_negative_int(
                row.get("OPEN_CASE_COUNT"), "OPEN_CASE_COUNT"
            ),
            "HIGH_RISK_CASE_COUNT": parse_non_negative_int(
                row.get("HIGH_RISK_COUNT"), "HIGH_RISK_COUNT"
            ),
            "OVERDUE_CASE_COUNT": parse_non_negative_int(
                row.get("OVERDUE_COUNT"), "OVERDUE_COUNT"
            ),
        }
        normalized.append(
            {
                "OFFICER_ID": clean(str(row.get("OFFICER_LOGIN", ""))),
                "TEAM_CODE": clean(str(row.get("TEAM_CODE", ""))),
                "OPEN_CASE_COUNT": str(counts["OPEN_CASE_COUNT"]),
                "HIGH_RISK_CASE_COUNT": str(counts["HIGH_RISK_CASE_COUNT"]),
                "OVERDUE_CASE_COUNT": str(counts["OVERDUE_CASE_COUNT"]),
            }
        )
    return normalized


def split_risk_trends(
    rows: Iterable[dict[str, object]],
    business_date: date,
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    daily: list[dict[str, str]] = []
    weekly: list[dict[str, str]] = []
    exceptions: list[dict[str, str]] = []
    seven_days_ago = business_date.toordinal() - 6
    for row in rows:
        row_date = parse_iso_date(str(row.get("SUMMARY_DATE", "")))
        risk_band = clean(str(row.get("RISK_BAND", ""))).upper()
        count_value = clean(str(row.get("CASE_COUNT", "")))
        row_dict = {
            "SUMMARY_DATE": row_date.isoformat(),
            "RISK_BAND": risk_band,
            "CASE_COUNT": count_value,
        }
        if risk_band not in RISK_BAND_MAP or not count_value.isdigit():
            exceptions.append(row_dict)
            continue
        if row_date == business_date:
            daily.append(row_dict)
        if row_date.toordinal() >= seven_days_ago:
            weekly.append(row_dict)
    return daily, weekly, exceptions


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_sheet_xml(headers: list[str], rows: list[list[str]]) -> bytes:
    worksheet = ET.Element(
        "worksheet",
        xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    )
    sheet_data = ET.SubElement(worksheet, "sheetData")
    for row_index, values in enumerate([headers] + rows, start=1):
        row_elem = ET.SubElement(sheet_data, "row", r=str(row_index))
        for column_index, value in enumerate(values, start=1):
            cell = ET.SubElement(row_elem, "c", r=f"{column_letter(column_index)}{row_index}", t="inlineStr")
            is_elem = ET.SubElement(cell, "is")
            text_elem = ET.SubElement(is_elem, "t")
            text_elem.text = value
    return ET.tostring(worksheet, encoding="utf-8", xml_declaration=True)


def column_letter(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def write_simple_xlsx(
    path: Path,
    sheets: dict[str, list[dict[str, str]]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
""" + "".join(
                f'  <Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>\n'
                for i in range(1, len(sheets) + 1)
            ) + "</Types>",
        )
        zf.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>""",
        )
        zf.writestr(
            "docProps/core.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:dcmitype="http://purl.org/dc/dcmitype/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>Risk Trend Summary</dc:title>
  <dc:creator>OpenAI Codex</dc:creator>
  <dcterms:created xsi:type="dcterms:W3CDTF">{utc_now()}</dcterms:created>
</cp:coreProperties>""",
        )
        zf.writestr(
            "docProps/app.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
 xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Python</Application>
</Properties>""",
        )
        workbook_sheets = []
        workbook_rels = []
        for index, (sheet_name, rows) in enumerate(sheets.items(), start=1):
            workbook_sheets.append(
                f'<sheet name="{sheet_name}" sheetId="{index}" r:id="rId{index}"/>'
            )
            workbook_rels.append(
                f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
            )
            headers = list(rows[0].keys()) if rows else ["INFO"]
            row_values = [list(item.values()) for item in rows] if rows else [["No rows"]]
            zf.writestr(f"xl/worksheets/sheet{index}.xml", build_sheet_xml(headers, row_values))
        zf.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>"""
            + "".join(workbook_sheets)
            + "</sheets></workbook>",
        )
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">"""
            + "".join(workbook_rels)
            + "</Relationships>",
        )


def create_sharepoint_client():
    try:
        import requests  # type: ignore
    except ImportError as exc:
        raise RuntimeError("requests is required for SharePoint uploads.") from exc
    return requests.Session()


def upload_file_to_sharepoint(session, site_url: str, library_path: str, file_path: Path) -> None:
    token = get_env("SHAREPOINT_ACCESS_TOKEN")
    target_url = f"{site_url.rstrip('/')}/{library_path.strip('/')}/{file_path.name}"
    with file_path.open("rb") as handle:
        response = session.put(
            target_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/octet-stream",
            },
            data=handle.read(),
            timeout=120,
        )
    response.raise_for_status()


def run_transformation(
    business_date_value: str,
    output_dir: Path,
    region_code: str | None,
    upload_to_sharepoint: bool,
) -> dict[str, int]:
    business_date = datetime.strptime(business_date_value, "%Y%m%d").date()
    output_dir.mkdir(parents=True, exist_ok=True)

    result_sets = fetch_result_sets(business_date.isoformat(), region_code)
    open_case_rows = normalize_open_cases(result_sets["OPEN_CASE_DETAIL"], business_date)
    workload_rows = normalize_workload(result_sets["OFFICER_WORKLOAD_SUMMARY"])
    daily_rows, weekly_rows, exception_rows = split_risk_trends(
        result_sets["RISK_TREND_SUMMARY"], business_date
    )

    open_case_path = output_dir / f"open_case_detail_{business_date_value}.csv"
    workload_path = output_dir / f"officer_workload_summary_{business_date_value}.csv"
    trend_path = output_dir / f"risk_trend_summary_{business_date_value}.xlsx"
    upload_manifest_path = output_dir / f"upload_manifest_{business_date_value}.csv"

    write_csv(open_case_path, OPEN_CASE_FIELDS, open_case_rows)
    write_csv(workload_path, WORKLOAD_FIELDS, workload_rows)
    write_simple_xlsx(
        trend_path,
        {
            "daily_summary": daily_rows,
            "weekly_summary": weekly_rows,
            "exceptions": exception_rows,
        },
    )

    manifest_rows = [
        {
            "FILE_NAME": open_case_path.name,
            "TARGET_FOLDER": get_env("SHAREPOINT_LIBRARY_PATH", "ComplianceAnalytics"),
            "ROW_COUNT": str(len(open_case_rows)),
            "PUBLISHED_AT": utc_now(),
            "STATUS": "READY",
        },
        {
            "FILE_NAME": workload_path.name,
            "TARGET_FOLDER": get_env("SHAREPOINT_LIBRARY_PATH", "ComplianceAnalytics"),
            "ROW_COUNT": str(len(workload_rows)),
            "PUBLISHED_AT": utc_now(),
            "STATUS": "READY",
        },
        {
            "FILE_NAME": trend_path.name,
            "TARGET_FOLDER": get_env("SHAREPOINT_LIBRARY_PATH", "ComplianceAnalytics"),
            "ROW_COUNT": str(len(daily_rows) + len(weekly_rows) + len(exception_rows)),
            "PUBLISHED_AT": utc_now(),
            "STATUS": "READY",
        },
    ]
    write_csv(upload_manifest_path, UPLOAD_MANIFEST_FIELDS, manifest_rows)

    if upload_to_sharepoint:
        session = create_sharepoint_client()
        site_url = get_env("SHAREPOINT_SITE_URL")
        library_path = get_env("SHAREPOINT_LIBRARY_PATH")
        for file_path in (open_case_path, workload_path, trend_path, upload_manifest_path):
            upload_file_to_sharepoint(session, site_url, library_path, file_path)

    summary = {
        "open_case_rows": len(open_case_rows),
        "workload_rows": len(workload_rows),
        "daily_trend_rows": len(daily_rows),
        "weekly_trend_rows": len(weekly_rows),
        "exception_rows": len(exception_rows),
    }
    (output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract Oracle PL/SQL compliance analytics and publish curated outputs for SharePoint.")
    parser.add_argument("--business-date", required=True, help="Business date in YYYYMMDD format.")
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory for generated outputs.")
    parser.add_argument("--region-code", default=None, help="Optional regional filter passed to the PL/SQL package.")
    parser.add_argument(
        "--upload-to-sharepoint",
        action="store_true",
        help="If set, upload generated files to SharePoint after local generation.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    summary = run_transformation(
        business_date_value=args.business_date,
        output_dir=args.output_dir,
        region_code=args.region_code,
        upload_to_sharepoint=args.upload_to_sharepoint,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
