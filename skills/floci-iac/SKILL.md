---
name: floci-iac
description: Export the resources in the local emulator as Terraform or CDK, and check a Terraform or CDK project for drift against what is actually running. Use when the user wants infrastructure code from a working local stack, or asks whether code and emulator agree.
argument-hint: "[terraform|cdk] | drift [path]"
---

# Floci infrastructure as code

Two jobs: export what exists, and compare code against it.

**Toolsets needed:** `core` (default), `hybrid` for the export tools and `ops` for the drift tools. `hybrid` and `ops` are not enabled by default; if a tool is missing, say which toolset to add to `FLOCI_TOOLSETS`.

## Export

1. Call `list_aws_services` to confirm there is something to export.
2. Call `export_to_terraform` with `format` set to `terraform` (default) or `cdk` from `$ARGUMENTS`.
3. Show the code in a fenced block (`hcl` for Terraform, `typescript` for CDK).
4. List which resource types were covered and which were empty. It covers S3, SQS, DynamoDB, Lambda and KMS only; say so.

## Drift

When `$ARGUMENTS` starts with `drift`:

1. Call `detect_iac_drift` with the path (current directory if omitted).
2. Report three lists: **missing** (in code, not running), **unmanaged** (running, not in code), **managed** (in sync).
3. Offer `discover_iac_resources` for the raw inventory of what the code declares.

## Recipes to Terraform

If recipes are running, `export_recipes_to_terraform` maps each to its managed AWS service. Passwords come out as sensitive Terraform variables.
