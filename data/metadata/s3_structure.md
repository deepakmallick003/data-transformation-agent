## S3 Storage Model

This file defines the S3 layout used by this repo.

## Shared Source Material

Source material lives directly under the configured bucket by source area.

```text
s3://<shared-bucket>/
└── <source-area>/
    ├── primary-source.ext
    ├── supplementary-source.ext
    └── rules.ext
```

## Agent Result Storage

When request files are stored in S3, the layout is:

```text
s3://<S3_BUCKET>/
└── agents/
    └── <agent-name>/
        └── results/
            └── <request_id>/
                ├── request/
                └── deliverables/
```

## Bootstrap

During `prepare` and `deploy`, the shared bucket should include:

```text
agents/
agents/<agent-name>/
agents/<agent-name>/results/
```
