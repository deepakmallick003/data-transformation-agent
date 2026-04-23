# Compliance Cases Oracle To SharePoint Code Bundle

## What This Bundle Does

This bundle extracts compliance analytics result sets from an Oracle PL/SQL package, normalizes the
returned rows, generates curated CSV and XLSX outputs, and can optionally upload those outputs to a
SharePoint document library.

## Source Documents Used

In this request output, the transformation documents used to generate this code are staged under:

`../transformation-documents/compliance-cases-oracle-to-sharepoint/`

In the downloadable bundle, those same documents are included under:

`transformation-documents/compliance-cases-oracle-to-sharepoint/`

## Generated Files

- `transformation.py`
- `.env.example`
- `compliance-cases-oracle-to-sharepoint.yaml`

## Known Assumptions And Gaps

- Oracle extraction expects the PL/SQL package `HMRC_COMPLIANCE_ANALYTICS_PKG.EXPORT_CASE_ANALYTICS`
- the implementation assumes the package returns three cursor-like result sets
- SharePoint publication uses HTTP upload semantics with bearer-token auth, which may need adaptation to the real tenancy API shape
- workbook generation is implemented as a lightweight XLSX writer to avoid hard dependency on spreadsheet libraries
- officer hierarchy and region taxonomy dependencies are noted in the documents but are not separately loaded because their exact source contracts were not provided

## Required Environment Variables

See `.env.example` for placeholders. The minimum required values are:

- `ORACLE_DSN`
- `ORACLE_USER`
- `ORACLE_PASSWORD`

If uploading to SharePoint:

- `SHAREPOINT_SITE_URL`
- `SHAREPOINT_LIBRARY_PATH`
- `SHAREPOINT_ACCESS_TOKEN`

## How To Run

```bash
python3 transformation.py \
  --business-date 20260423 \
  --output-dir /tmp/compliance_cases_to_sharepoint
```

To publish the generated outputs to SharePoint:

```bash
python3 transformation.py \
  --business-date 20260423 \
  --output-dir /tmp/compliance_cases_to_sharepoint \
  --region-code WM \
  --upload-to-sharepoint
```

## Local Output Files

The output directory will contain:

- `open_case_detail_YYYYMMDD.csv`
- `officer_workload_summary_YYYYMMDD.csv`
- `risk_trend_summary_YYYYMMDD.xlsx`
- `upload_manifest_YYYYMMDD.csv`
- `run_summary.json`
