# Customs Declaration PDF To Snowflake Code Bundle

## What This Bundle Does

This bundle generates structured customs declaration outputs from:

- a manifest JSON stored in S3
- a declaration index CSV stored in S3
- customs declaration PDF documents stored in S3

The generated Python script parses declaration PDFs, joins them to batch metadata, validates the
extracted content, writes local staged outputs, and can optionally load accepted rows into
Snowflake.

## Source Documents Used

In this request output, the transformation documents used to generate this code are staged under:

`../transformation-documents/customs-declaration-pdf-to-snowflake/`

In the downloadable bundle, those same documents are included under:

`transformation-documents/customs-declaration-pdf-to-snowflake/`

## Generated Files

- `transformation.py`
- `.env.example`
- `customs-declaration-pdf-to-snowflake.yaml`

## Known Assumptions And Gaps

- PDF parsing depends on `pypdf`
- S3 access depends on `boto3`
- Snowflake loading depends on `snowflake-connector-python`
- commodity-line extraction assumes the PDF text follows a repeatable line pattern
- customs reference data validation is partially implied by the documents but not fully implemented because the documents do not provide the reference feed shape
- the script produces local staged CSV outputs even when Snowflake loading is disabled

## Required Environment Variables

See `.env.example` for placeholders. The minimum required values are:

- `AWS_REGION`
- `SOURCE_S3_BUCKET`
- `MANIFEST_KEY_TEMPLATE`
- `INDEX_KEY_TEMPLATE`

If loading to Snowflake:

- `SNOWFLAKE_ACCOUNT`
- `SNOWFLAKE_USER`
- `SNOWFLAKE_PASSWORD`
- `SNOWFLAKE_WAREHOUSE`
- `SNOWFLAKE_DATABASE`
- `SNOWFLAKE_SCHEMA`

## How To Run

```bash
python3 transformation.py \
  --business-date 20260422 \
  --output-dir /tmp/customs_pdf_to_snowflake
```

To also load accepted rows into Snowflake:

```bash
python3 transformation.py \
  --business-date 20260422 \
  --output-dir /tmp/customs_pdf_to_snowflake \
  --load-to-snowflake
```

## Local Output Files

The output directory will contain:

- `curated_customs_declaration_header.csv`
- `curated_customs_declaration_line.csv`
- `customs_declaration_rejection_log.csv`
- `run_summary.json`
