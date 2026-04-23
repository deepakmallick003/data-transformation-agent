# ETMP To MDM VAT Python Bundle

## What This Bundle Does

This bundle turns the staged ETMP to MDM VAT transformation documents into a runnable local Python
implementation.

You can extract this bundle and run it from any directory. It does not need to stay inside the
original repository layout.

The main script:

- reads `VAT_RETURN_HEADER`, `VAT_RETURN_LINE`, and `TAXPAYER_REG` feed extracts
- applies the mappings and validation rules described in the transformation documents
- produces local CSV outputs for:
  - `DIM_TAXPAYER`
  - `FACT_VAT_RETURN`
  - `FACT_VAT_RETURN_LINE`
  - `ERROR_LOG`

## Source Documents Used

In this request output, the transformation documents used to generate this code are staged once
under:

`../transformation-documents/etmp-to-mdm-vat/`

In the downloadable bundle, those same documents are included under:

`transformation-documents/etmp-to-mdm-vat/`

Those source documents are:

- `data-feed-specification-document.md`
- `data-feed-transformation-document.md`
- `data-feed-interdependencies-document.md`

## What Is Runnable Now

The script is runnable as a local file-based implementation slice.

It supports:

- pipe-delimited `.csv` input files
- pipe-delimited `.csv.gz` input files
- document-grounded validation and rejection rules
- bounded SCD Type 2 handling for `DIM_TAXPAYER`
- optional reference extracts for sector and date lookups

## Known Boundaries

This is not a production-faithful orchestration bundle yet.

Current bounded assumptions:

- encrypted `.enc` source files must be decrypted before running the script
- if no `DIM_DATE` extract is provided, `DATE_KEY` values are derived as `YYYYMMDD`
- if no sector reference extract is provided, the sample sector lookup in the document appendix is used
- true warehouse sequence generation is represented by local deterministic counters
- cross-run duplicate detection for facts is limited because target-state access is not available

## How To Run

```bash
python3 transformation.py \
  --header /path/to/VAT_RETURN_HEADER_20260414.csv \
  --lines /path/to/VAT_RETURN_LINE_20260414.csv \
  --taxpayer /path/to/TAXPAYER_REG_20260414.csv \
  --output-dir /tmp/etmp_to_mdm_vat_output
```

Optional inputs:

```bash
python3 transformation.py \
  --header /path/to/VAT_RETURN_HEADER_20260414.csv.gz \
  --lines /path/to/VAT_RETURN_LINE_20260414.csv.gz \
  --taxpayer /path/to/TAXPAYER_REG_20260414.csv.gz \
  --sector-ref /path/to/ref_sector_codes.csv \
  --date-dimension /path/to/dim_date.csv \
  --existing-dim-taxpayer /path/to/dim_taxpayer.csv \
  --load-date 2026-04-14 \
  --output-dir /tmp/etmp_to_mdm_vat_output
```

## Output Files

The output directory will contain:

- `dim_taxpayer.csv`
- `fact_vat_return.csv`
- `fact_vat_return_line.csv`
- `error_log.csv`
- `run_summary.json`

## Handoff Files

The request output also includes:

- `transformation.py`
- `README.md`
- `../transformation-documents/etmp-to-mdm-vat/`
- `../etmp-to-mdm-vat-code-bundle.zip`
