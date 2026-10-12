---
name: floci-multicloud
description: Compare the same kinds of resources (object storage, queues and topics, secrets) across the local AWS, Azure, GCP and OCI runtimes in one table. Use when the user wants a cross-cloud inventory, or asks where something exists.
argument-hint: "[storage | messaging | secrets]  (default: all)"
---

# Floci multi-cloud inventory

Read the equivalent resources from every cloud that answers and line them up.

**Toolsets needed:** `core` and `storage` and `messaging` (all enabled by default).

## Steps

1. Call `list_clouds`. Only query clouds reported `online`; say which were skipped.
2. For each online cloud, gather what `$ARGUMENTS` asks for (everything if empty):

   | Kind | AWS | Azure | GCP | OCI |
   |---|---|---|---|---|
   | Object storage | `list_s3_buckets` | `azure_list_containers` | `gcp_list_buckets` | `oci_list_buckets` |
   | Queues and topics | `list_sqs_queues`, `list_sns_topics` | `azure_list_queues` | `gcp_list_topics` | not covered |
   | Secrets | `list_secrets` | `azure_list_secrets` | `gcp_list_secrets` | not covered |

3. Optionally call the matching `*_list_objects` / `list_s3_objects` for one bucket per cloud when the user asks for contents.

## Output

A table per kind, one column per cloud, resource names in the cells. Mark `n/a` where the tool set does not cover that kind for a cloud.

Secret tools return names only. Never try to read or print secret values unless the user explicitly asks for one named secret, and then use `get_secret_value` on AWS only.
