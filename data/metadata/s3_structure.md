## S3 Storage Model

This file defines the S3 read layout, the primary S3 write layout, and the local fallback layout used by this repo.

This layout applies when a skill explicitly uses the S3 write path.
It is not the default storage behavior for every run.

## Read Sources

Source material lives under the configured S3 read bucket and prefix.

```text
s3://<S3_READ_BUCKET>/<S3_READ_PREFIX>
└── <source-area>/
    ├── primary-source.ext
    ├── supplementary-source.ext
    └── rules.ext
```

## Primary Request Writes

Agent-produced request files are stored under the configured S3 write bucket and prefix.

```text
s3://<S3_WRITE_BUCKET>/<S3_WRITE_PREFIX>/<agent_name>/results/
├── raw/
│   └── <request_id>/
└── processed/
    └── <request_id>/
```

## Local Fallback

If S3 write is not configured or is unavailable at runtime, request files fall back to local storage.

```text
results/
├── raw/
│   └── <request_id>/
└── processed/
    └── <request_id>/
```
