"""Generate VAT warehouse-ready outputs from the ETMP to MDM VAT document set.

This script is intended to be runnable as a portable bundle after extraction from its zip archive.

Bounded implementation assumptions:
- Input files are already decrypted. `.csv` and `.csv.gz` are supported.
- If no date-dimension extract is provided, DATE_KEY values are derived as YYYYMMDD.
- If no sector reference extract is provided, the sample sector codes from the document
  appendix are used as a minimal lookup.
- If no existing DIM_TAXPAYER extract is provided, SCD comparison is performed only
  within the current run.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable
import calendar


DEFAULT_SECTOR_LOOKUP = {
    "C25": "Manufacture of fabricated metal products",
    "G46": "Wholesale trade, except of motor vehicles and motorcycles",
    "G47": "Retail trade, except of motor vehicles and motorcycles",
    "J62": "Computer programming, consultancy and related activities",
    "M69": "Legal and accounting activities",
}

ALLOWED_RETURN_TYPES = {"Standard", "Correction", "Nil"}
VALID_BOX_NUMBERS = {str(value) for value in range(1, 10)}

MANDATORY_FIELDS = {
    "header": [
        "RETURN_ID",
        "VRN",
        "PERIOD_KEY",
        "SUBMISSION_DATE",
        "SUBMISSION_TIME",
        "RETURN_TYPE",
        "FILING_FREQUENCY",
        "CREATED_DATE",
    ],
    "line": [
        "RETURN_LINE_ID",
        "RETURN_ID",
        "BOX_NUMBER",
        "CURRENCY_CODE",
        "CREATED_DATE",
    ],
    "taxpayer": [
        "VRN",
        "BUSINESS_NAME",
        "REGISTRATION_DATE",
        "STATUS",
    ],
}

DIM_COMPARE_FIELDS = [
    "BUSINESS_NAME",
    "TRADE_NAME",
    "BUSINESS_TYPE",
    "SECTOR_CODE",
    "STATUS",
]

DIM_TAXPAYER_FIELDNAMES = [
    "TAXPAYER_KEY",
    "VRN",
    "BUSINESS_NAME",
    "TRADE_NAME",
    "REGISTRATION_DATE",
    "DEREGISTRATION_DATE",
    "BUSINESS_TYPE",
    "SECTOR_CODE",
    "SECTOR_DESCRIPTION",
    "STATUS",
    "EFFECTIVE_FROM_DATE",
    "EFFECTIVE_TO_DATE",
    "CURRENT_FLAG",
    "LOAD_DATE",
]

FACT_VAT_RETURN_FIELDNAMES = [
    "VAT_RETURN_KEY",
    "TAXPAYER_KEY",
    "SUBMISSION_DATE_KEY",
    "PERIOD_DATE_KEY",
    "RETURN_ID",
    "RETURN_TYPE",
    "FILING_FREQUENCY",
    "SUBMISSION_TIMESTAMP",
    "TOTAL_VAT_DUE",
    "LOAD_DATE",
]

FACT_VAT_RETURN_LINE_FIELDNAMES = [
    "VAT_RETURN_LINE_KEY",
    "VAT_RETURN_KEY",
    "RETURN_LINE_ID",
    "BOX_NUMBER",
    "BOX_DESCRIPTION",
    "BOX_VALUE",
    "CURRENCY_CODE",
    "LOAD_DATE",
]

ERROR_LOG_FIELDNAMES = [
    "ERROR_ID",
    "FEED_NAME",
    "FILE_NAME",
    "RECORD_KEY",
    "ERROR_CODE",
    "ERROR_MESSAGE",
    "SOURCE_RECORD",
    "ERROR_TIMESTAMP",
]


@dataclass
class ErrorRecord:
    error_id: int
    feed_name: str
    file_name: str
    record_key: str
    error_code: str
    error_message: str
    source_record: str
    error_timestamp: str

    def to_row(self) -> dict[str, str]:
        return {
            "ERROR_ID": str(self.error_id),
            "FEED_NAME": self.feed_name,
            "FILE_NAME": self.file_name,
            "RECORD_KEY": self.record_key,
            "ERROR_CODE": self.error_code,
            "ERROR_MESSAGE": self.error_message,
            "SOURCE_RECORD": self.source_record,
            "ERROR_TIMESTAMP": self.error_timestamp,
        }


def strip_non_printable(value: str | None) -> str:
    if value is None:
        return ""
    return "".join(char for char in value if ord(char) >= 32).strip()


def normalize_text(value: str | None, uppercase: bool = False) -> str:
    cleaned = strip_non_printable(value)
    return cleaned.upper() if uppercase and cleaned else cleaned


def parse_required_date(raw_value: str | None) -> date:
    value = strip_non_printable(raw_value)
    if not value or value == "9999-12-31":
        raise ValueError("Date is missing or invalid")
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_optional_date(raw_value: str | None) -> date | None:
    value = strip_non_printable(raw_value)
    if not value:
        return None
    if value == "9999-12-31":
        raise ValueError("Date is invalid")
    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_submission_timestamp(submission_date: date, raw_time: str | None) -> datetime:
    value = strip_non_printable(raw_time)
    if not value:
        raise ValueError("Submission time is missing")
    parsed_time = datetime.strptime(value, "%H:%M:%S").time()
    return datetime.combine(submission_date, parsed_time)


def parse_decimal(raw_value: str | None) -> Decimal | None:
    value = strip_non_printable(raw_value)
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid numeric value: {value}") from exc


def ensure_mandatory_fields(
    record: dict[str, str],
    required_fields: Iterable[str],
) -> str | None:
    for field_name in required_fields:
        if not strip_non_printable(record.get(field_name)):
            return field_name
    return None


def validate_vrn(vrn: str) -> bool:
    return len(vrn) == 9 and vrn.isdigit()


def period_key_to_month_end(period_key: str) -> date:
    value = strip_non_printable(period_key)
    if len(value) != 6 or not value.isdigit():
        raise ValueError("PERIOD_KEY must be in YYYYMM format")
    year = int(value[:4])
    month = int(value[4:6])
    if month < 1 or month > 12:
        raise ValueError("PERIOD_KEY month is invalid")
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day)


def date_to_key(
    date_value: date,
    date_lookup: dict[str, str] | None,
) -> str:
    iso_value = date_value.isoformat()
    if date_lookup is None:
        return date_value.strftime("%Y%m%d")
    if iso_value not in date_lookup:
        raise LookupError(f"Date {iso_value} not found in DIM_DATE")
    return date_lookup[iso_value]


def next_sequence(start_value: int):
    current = start_value
    while True:
        yield current
        current += 1


def open_text_file(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return path.open("r", encoding="utf-8", newline="")


def read_delimited_rows(path: Path, delimiter: str = "|") -> list[dict[str, str]]:
    with open_text_file(path) as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_sector_lookup(path: Path | None) -> dict[str, str]:
    if path is None:
        return dict(DEFAULT_SECTOR_LOOKUP)

    rows = read_csv_rows(path)
    lookup: dict[str, str] = {}
    for row in rows:
        sector_code = strip_non_printable(
            row.get("SECTOR_CODE") or row.get("sector_code")
        )
        description = strip_non_printable(
            row.get("SECTOR_DESCRIPTION") or row.get("sector_description")
        )
        if sector_code:
            lookup[sector_code] = description
    return lookup


def load_date_lookup(path: Path | None) -> dict[str, str] | None:
    if path is None:
        return None

    rows = read_csv_rows(path)
    lookup: dict[str, str] = {}
    for row in rows:
        date_value = strip_non_printable(row.get("DATE_VALUE") or row.get("date_value"))
        date_key = strip_non_printable(row.get("DATE_KEY") or row.get("date_key"))
        if date_value and date_key:
            lookup[date_value] = date_key
    return lookup


def load_existing_dim_taxpayer(
    path: Path | None,
) -> tuple[list[dict[str, str]], dict[str, dict[str, str]], int]:
    if path is None or not path.exists():
        return [], {}, 100234

    rows = read_csv_rows(path)
    current_by_vrn: dict[str, dict[str, str]] = {}
    max_key = 100233
    for row in rows:
        try:
            max_key = max(max_key, int(row["TAXPAYER_KEY"]))
        except (KeyError, ValueError):
            continue
        if row.get("CURRENT_FLAG") == "Y":
            current_by_vrn[row.get("VRN", "")] = row
    return rows, current_by_vrn, max_key + 1


def serialize_record(record: dict[str, str]) -> str:
    return json.dumps(record, sort_keys=True)


def add_error(
    error_rows: list[dict[str, str]],
    error_counter: list[int],
    feed_name: str,
    file_name: str,
    record_key: str,
    error_code: str,
    error_message: str,
    record: dict[str, str],
) -> None:
    error_counter[0] += 1
    error = ErrorRecord(
        error_id=error_counter[0],
        feed_name=feed_name,
        file_name=file_name,
        record_key=record_key,
        error_code=error_code,
        error_message=error_message,
        source_record=serialize_record(record),
        error_timestamp=(
            datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        ),
    )
    error_rows.append(error.to_row())


def normalised_compare_view(row: dict[str, str]) -> dict[str, str]:
    return {
        "BUSINESS_NAME": normalize_text(row.get("BUSINESS_NAME"), uppercase=True),
        "TRADE_NAME": normalize_text(row.get("TRADE_NAME"), uppercase=True),
        "BUSINESS_TYPE": normalize_text(row.get("BUSINESS_TYPE")),
        "SECTOR_CODE": normalize_text(row.get("SECTOR_CODE")),
        "STATUS": normalize_text(row.get("STATUS")),
    }


def build_taxpayer_row(
    source_row: dict[str, str],
    taxpayer_key: int,
    load_date_iso: str,
    sector_lookup: dict[str, str],
    effective_from_date: date,
) -> dict[str, str]:
    sector_code = normalize_text(source_row.get("SECTOR_CODE"))
    deregistration_date = parse_optional_date(source_row.get("DEREGISTRATION_DATE"))
    return {
        "TAXPAYER_KEY": str(taxpayer_key),
        "VRN": normalize_text(source_row.get("VRN")),
        "BUSINESS_NAME": normalize_text(source_row.get("BUSINESS_NAME"), uppercase=True),
        "TRADE_NAME": normalize_text(source_row.get("TRADE_NAME"), uppercase=True),
        "REGISTRATION_DATE": parse_required_date(
            source_row.get("REGISTRATION_DATE")
        ).isoformat(),
        "DEREGISTRATION_DATE": (
            deregistration_date.isoformat() if deregistration_date is not None else ""
        ),
        "BUSINESS_TYPE": normalize_text(source_row.get("BUSINESS_TYPE")),
        "SECTOR_CODE": sector_code,
        "SECTOR_DESCRIPTION": sector_lookup.get(sector_code, ""),
        "STATUS": normalize_text(source_row.get("STATUS")),
        "EFFECTIVE_FROM_DATE": effective_from_date.isoformat(),
        "EFFECTIVE_TO_DATE": "",
        "CURRENT_FLAG": "Y",
        "LOAD_DATE": load_date_iso,
    }


def run_transformation(
    header_path: Path,
    line_path: Path,
    taxpayer_path: Path,
    output_dir: Path,
    sector_ref_path: Path | None = None,
    existing_dim_taxpayer_path: Path | None = None,
    date_dimension_path: Path | None = None,
    load_date_value: str | None = None,
) -> dict[str, int]:
    load_date = (
        datetime.strptime(load_date_value, "%Y-%m-%d").date()
        if load_date_value
        else date.today()
    )
    load_date_iso = load_date.isoformat()
    output_dir.mkdir(parents=True, exist_ok=True)

    sector_lookup = load_sector_lookup(sector_ref_path)
    date_lookup = load_date_lookup(date_dimension_path)
    dim_taxpayer_rows, current_taxpayer_by_vrn, next_taxpayer_key_start = (
        load_existing_dim_taxpayer(existing_dim_taxpayer_path)
    )
    taxpayer_key_seq = next_sequence(next_taxpayer_key_start)
    vat_return_key_seq = next_sequence(500012345)
    vat_return_line_key_seq = next_sequence(700012345678)

    fact_vat_return_rows: list[dict[str, str]] = []
    fact_vat_return_line_rows: list[dict[str, str]] = []
    error_rows: list[dict[str, str]] = []
    error_counter = [0]

    for row in read_delimited_rows(taxpayer_path):
        record_key = strip_non_printable(row.get("VRN"))
        missing_field = ensure_mandatory_fields(row, MANDATORY_FIELDS["taxpayer"])
        if missing_field:
            add_error(
                error_rows,
                error_counter,
                "TAXPAYER_REG",
                taxpayer_path.name,
                record_key,
                "MISSING_FIELD",
                f"Missing mandatory field: {missing_field}",
                row,
            )
            continue

        try:
            registration_date = parse_required_date(row.get("REGISTRATION_DATE"))
            parse_optional_date(row.get("DEREGISTRATION_DATE"))
            updated_date = parse_optional_date(row.get("UPDATED_DATE"))
        except ValueError as exc:
            add_error(
                error_rows,
                error_counter,
                "TAXPAYER_REG",
                taxpayer_path.name,
                record_key,
                "INVALID_DATE",
                str(exc),
                row,
            )
            continue

        if not validate_vrn(record_key):
            add_error(
                error_rows,
                error_counter,
                "TAXPAYER_REG",
                taxpayer_path.name,
                record_key,
                "INVALID_VRN",
                "VRN must be exactly 9 numeric characters.",
                row,
            )
            continue

        compare_view = normalised_compare_view(row)
        current_row = current_taxpayer_by_vrn.get(record_key)
        if current_row is not None:
            existing_compare = {field: current_row.get(field, "") for field in DIM_COMPARE_FIELDS}
            if existing_compare == compare_view:
                continue
            current_row["CURRENT_FLAG"] = "N"
            current_row["EFFECTIVE_TO_DATE"] = load_date_iso

        effective_from = updated_date or load_date
        taxpayer_row = build_taxpayer_row(
            source_row=row,
            taxpayer_key=next(taxpayer_key_seq),
            load_date_iso=load_date_iso,
            sector_lookup=sector_lookup,
            effective_from_date=effective_from,
        )
        dim_taxpayer_rows.append(taxpayer_row)
        current_taxpayer_by_vrn[record_key] = taxpayer_row

    accepted_headers: dict[str, dict[str, str]] = {}
    seen_return_ids: set[str] = set()

    for row in read_delimited_rows(header_path):
        return_id = strip_non_printable(row.get("RETURN_ID"))
        missing_field = ensure_mandatory_fields(row, MANDATORY_FIELDS["header"])
        if missing_field:
            add_error(
                error_rows,
                error_counter,
                "VAT_RETURN_HEADER",
                header_path.name,
                return_id,
                "MISSING_FIELD",
                f"Missing mandatory field: {missing_field}",
                row,
            )
            continue

        if return_id in seen_return_ids:
            add_error(
                error_rows,
                error_counter,
                "VAT_RETURN_HEADER",
                header_path.name,
                return_id,
                "DUPLICATE_KEY",
                "Duplicate RETURN_ID detected in header feed.",
                row,
            )
            continue
        seen_return_ids.add(return_id)

        vrn = normalize_text(row.get("VRN"))
        if not validate_vrn(vrn):
            add_error(
                error_rows,
                error_counter,
                "VAT_RETURN_HEADER",
                header_path.name,
                return_id,
                "INVALID_VRN",
                "VRN must be exactly 9 numeric characters.",
                row,
            )
            continue

        try:
            submission_date = parse_required_date(row.get("SUBMISSION_DATE"))
            parse_required_date(row.get("CREATED_DATE"))
            submission_timestamp = parse_submission_timestamp(
                submission_date, row.get("SUBMISSION_TIME")
            )
            period_end_date = period_key_to_month_end(normalize_text(row.get("PERIOD_KEY")))
        except ValueError as exc:
            add_error(
                error_rows,
                error_counter,
                "VAT_RETURN_HEADER",
                header_path.name,
                return_id,
                "INVALID_DATE",
                str(exc),
                row,
            )
            continue

        return_type = normalize_text(row.get("RETURN_TYPE"))
        if return_type not in ALLOWED_RETURN_TYPES:
            add_error(
                error_rows,
                error_counter,
                "VAT_RETURN_HEADER",
                header_path.name,
                return_id,
                "INVALID_RETURN_TYPE",
                "RETURN_TYPE must be Standard, Correction, or Nil.",
                row,
            )
            continue

        try:
            total_vat_due = parse_decimal(row.get("TOTAL_VAT_DUE"))
        except ValueError as exc:
            add_error(
                error_rows,
                error_counter,
                "VAT_RETURN_HEADER",
                header_path.name,
                return_id,
                "INVALID_VAT_AMOUNT",
                str(exc),
                row,
            )
            continue

        if return_type == "Standard" and total_vat_due is not None and total_vat_due < 0:
            add_error(
                error_rows,
                error_counter,
                "VAT_RETURN_HEADER",
                header_path.name,
                return_id,
                "INVALID_VAT_AMOUNT",
                "TOTAL_VAT_DUE must be >= 0 for Standard returns.",
                row,
            )
            continue

        taxpayer_row = current_taxpayer_by_vrn.get(vrn)
        if taxpayer_row is None:
            add_error(
                error_rows,
                error_counter,
                "VAT_RETURN_HEADER",
                header_path.name,
                return_id,
                "TAXPAYER_NOT_FOUND",
                "VRN not found in current DIM_TAXPAYER view.",
                row,
            )
            continue

        try:
            submission_date_key = date_to_key(submission_date, date_lookup)
            period_date_key = date_to_key(period_end_date, date_lookup)
        except LookupError as exc:
            add_error(
                error_rows,
                error_counter,
                "VAT_RETURN_HEADER",
                header_path.name,
                return_id,
                "DATE_LOOKUP_FAILED",
                str(exc),
                row,
            )
            continue

        fact_row = {
            "VAT_RETURN_KEY": str(next(vat_return_key_seq)),
            "TAXPAYER_KEY": taxpayer_row["TAXPAYER_KEY"],
            "SUBMISSION_DATE_KEY": submission_date_key,
            "PERIOD_DATE_KEY": period_date_key,
            "RETURN_ID": return_id,
            "RETURN_TYPE": return_type,
            "FILING_FREQUENCY": normalize_text(row.get("FILING_FREQUENCY")),
            "SUBMISSION_TIMESTAMP": submission_timestamp.isoformat(sep=" "),
            "TOTAL_VAT_DUE": "" if total_vat_due is None else f"{total_vat_due:.2f}",
            "LOAD_DATE": load_date_iso,
        }
        fact_vat_return_rows.append(fact_row)
        accepted_headers[return_id] = fact_row

    for row in read_delimited_rows(line_path):
        return_line_id = strip_non_printable(row.get("RETURN_LINE_ID"))
        missing_field = ensure_mandatory_fields(row, MANDATORY_FIELDS["line"])
        if missing_field:
            add_error(
                error_rows,
                error_counter,
                "VAT_RETURN_LINE",
                line_path.name,
                return_line_id,
                "MISSING_FIELD",
                f"Missing mandatory field: {missing_field}",
                row,
            )
            continue

        try:
            parse_required_date(row.get("CREATED_DATE"))
        except ValueError as exc:
            add_error(
                error_rows,
                error_counter,
                "VAT_RETURN_LINE",
                line_path.name,
                return_line_id,
                "INVALID_DATE",
                str(exc),
                row,
            )
            continue

        box_number = normalize_text(row.get("BOX_NUMBER"))
        if box_number not in VALID_BOX_NUMBERS:
            add_error(
                error_rows,
                error_counter,
                "VAT_RETURN_LINE",
                line_path.name,
                return_line_id,
                "INVALID_BOX",
                "BOX_NUMBER must be in the range 1-9.",
                row,
            )
            continue

        return_id = normalize_text(row.get("RETURN_ID"))
        fact_header = accepted_headers.get(return_id)
        if fact_header is None:
            add_error(
                error_rows,
                error_counter,
                "VAT_RETURN_LINE",
                line_path.name,
                return_line_id,
                "ORPHAN_RECORD",
                "No matching RETURN_ID found in accepted FACT_VAT_RETURN records.",
                row,
            )
            continue

        try:
            box_value = parse_decimal(row.get("BOX_VALUE"))
        except ValueError as exc:
            add_error(
                error_rows,
                error_counter,
                "VAT_RETURN_LINE",
                line_path.name,
                return_line_id,
                "INVALID_VAT_AMOUNT",
                str(exc),
                row,
            )
            continue

        final_box_value = Decimal("0") if box_value is None else box_value
        currency_code = normalize_text(row.get("CURRENCY_CODE")) or "GBP"
        fact_line_row = {
            "VAT_RETURN_LINE_KEY": str(next(vat_return_line_key_seq)),
            "VAT_RETURN_KEY": fact_header["VAT_RETURN_KEY"],
            "RETURN_LINE_ID": return_line_id,
            "BOX_NUMBER": box_number,
            "BOX_DESCRIPTION": normalize_text(row.get("BOX_DESCRIPTION")),
            "BOX_VALUE": f"{final_box_value:.2f}",
            "CURRENCY_CODE": currency_code,
            "LOAD_DATE": load_date_iso,
        }
        fact_vat_return_line_rows.append(fact_line_row)

    write_csv(output_dir / "dim_taxpayer.csv", DIM_TAXPAYER_FIELDNAMES, dim_taxpayer_rows)
    write_csv(
        output_dir / "fact_vat_return.csv",
        FACT_VAT_RETURN_FIELDNAMES,
        fact_vat_return_rows,
    )
    write_csv(
        output_dir / "fact_vat_return_line.csv",
        FACT_VAT_RETURN_LINE_FIELDNAMES,
        fact_vat_return_line_rows,
    )
    write_csv(output_dir / "error_log.csv", ERROR_LOG_FIELDNAMES, error_rows)

    summary = {
        "dim_taxpayer_rows": len(dim_taxpayer_rows),
        "fact_vat_return_rows": len(fact_vat_return_rows),
        "fact_vat_return_line_rows": len(fact_vat_return_line_rows),
        "error_rows": len(error_rows),
    }
    (output_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transform ETMP VAT feed extracts into MDM-style output files."
    )
    parser.add_argument("--header", required=True, type=Path, help="Path to VAT_RETURN_HEADER input.")
    parser.add_argument("--lines", required=True, type=Path, help="Path to VAT_RETURN_LINE input.")
    parser.add_argument("--taxpayer", required=True, type=Path, help="Path to TAXPAYER_REG input.")
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory where transformed output files will be written.",
    )
    parser.add_argument(
        "--sector-ref",
        type=Path,
        default=None,
        help="Optional CSV reference extract for sector descriptions.",
    )
    parser.add_argument(
        "--existing-dim-taxpayer",
        type=Path,
        default=None,
        help="Optional prior DIM_TAXPAYER extract for SCD Type 2 comparison.",
    )
    parser.add_argument(
        "--date-dimension",
        type=Path,
        default=None,
        help="Optional DIM_DATE extract containing DATE_VALUE and DATE_KEY columns.",
    )
    parser.add_argument(
        "--load-date",
        default=None,
        help="Override load date in YYYY-MM-DD format.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run_transformation(
        header_path=args.header,
        line_path=args.lines,
        taxpayer_path=args.taxpayer,
        output_dir=args.output_dir,
        sector_ref_path=args.sector_ref,
        existing_dim_taxpayer_path=args.existing_dim_taxpayer,
        date_dimension_path=args.date_dimension,
        load_date_value=args.load_date,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
