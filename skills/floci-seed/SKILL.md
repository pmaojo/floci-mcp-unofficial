---
name: floci-seed
description: Fill a local DynamoDB table, S3 bucket or PostgreSQL database with synthetic Faker data for development. Use when the user wants test data, fixtures, or an empty local resource populated.
argument-hint: "<dynamodb|s3|postgres> <name> [schema json]"
---

# Floci seed

Inject synthetic data with `seed_mock_data`.

**Toolsets needed:** `hybrid` (where `seed_mock_data` lives) and `storage`. `hybrid` is not enabled by default; if the tool is missing, tell the user to add it to `FLOCI_TOOLSETS` and restart.

## Arguments

`$ARGUMENTS`: `<target> <name> [schema_json]`

- `target`: `dynamodb`, `s3` or `postgres`
- `name`: table, bucket or database name
- `schema_json`: optional JSON object describing the data shape

## Steps

1. Parse the arguments.
2. For `dynamodb` call `list_dynamodb_tables`; for `s3` call `list_s3_buckets`. If the resource does not exist, ask whether to create it first (`create_dynamodb_table` or `create_s3_bucket`) instead of failing.
3. For `postgres`, a `connection_string` is required. Ask for it if missing, and never echo it back.
4. Call `seed_mock_data`.
5. Verify with `scan_dynamodb` (with a small `limit`) or `list_s3_objects` and report how many records were written and one sample.

## Rules

- Seeding writes to local emulators only. Do not point `connection_string` at a remote database unless the user says so explicitly.
