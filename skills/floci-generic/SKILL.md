---
name: floci-generic
description: Operate any service of the local AWS, Azure, GCP and OCI runtimes, and the Docker recipes, through the few generic tools instead of one tool per operation. Use when a request names a service or operation that no dedicated tool covers, or when it chains several calls or needs a big result filtered first.
argument-hint: "[what you want to do, e.g. 'list the queues with messages in them']"
---

# Floci generic

Reach every operation of every Floci runtime with `list_services`, `search_operations`, `describe_operation`, `call_read` and `call_write`. When a task chains calls or the result is large, run Python with `code_read` or `code_write` instead.

**Toolsets needed:** `generic` and `code` (neither is enabled by default). If `search_operations` is missing, call `enable_toolset` with `generic` when that tool exists; otherwise ask the user to add it to `FLOCI_TOOLSETS` and restart.

## The loop

1. **Find.** `search_operations` with what you want in plain words ("send a message to a queue"). Pass `cloud` (`aws`, `azure`, `gcp`, `oci`, `recipes`) and `service` when you know them. Each hit says `read` or `write`.
2. **Read the contract.** `describe_operation` gives the parameters (required ones marked), what comes back, and whether it is `destructive` or `sensitive`. Do not guess parameter names.
3. **Call.** `call_read` for a read. `call_write` for anything that changes state. A write sent to `call_read` is refused, by design.
4. **Say what you did.** Name the operation and the resource, not the tool.

## When to write code

Use `code_read` (or `code_write`) when one question needs several calls, or the raw answer is large:

```python
queues = aws("sqs", "ListQueues").get("QueueUrls", [])
result = {}
for url in queues:
    attrs = aws("sqs", "GetQueueAttributes", QueueUrl=url, AttributeNames=["ApproximateNumberOfMessages"])
    n = int(attrs["Attributes"]["ApproximateNumberOfMessages"])
    if n:
        result[url.rsplit("/", 1)[-1]] = n
```

`aws(service, operation, **params)` for AWS, `call(cloud, service, operation, **params)` for the rest, `rest(cloud, method, path, ...)` for a route nobody catalogued. Print or set `result`; filter in code so the answer stays small. Only the standard library is available.

## Per cloud

- **AWS**: parameter names are the service model's, in PascalCase (`QueueUrl`, `Bucket`). Floci implements a subset: if a service answers `NotImplemented`, say so rather than retrying. `list_services` with `probe=true` shows which services answer.
- **GCP**: names look like `ListTopics`, `CreateTopic`, or the full discovery id when two collide. Many parameters are full resource names (`{+parent}`, `{+name}`), for example `projects/floci-local/topics/events`; the project is defaulted when the path only needs it.
- **Azure**: data plane is `blob`, `queue`, `table`, `keyvault`. Everything else is ARM: service `arm` for subscriptions and resource groups, and a service per resource type that answers (`storage`, `sql`, `redis`, `vm`...) with `List`, `Get`, `Put` and `Delete`. Creating needs a resource group first, and `body` carries the resource.
- **OCI**: `compartmentId` is defaulted on lists and creates. Resources are addressed by `id` (an OCID). Object Storage is namespaced; the namespace is looked up for you.
- **recipes**: `ListRecipes`, `GetRecipe`, `DeployRecipe`, `TeardownRecipe`. Prefer the one marked `floci_native` as the AWS service instead. See the `floci-marketplace` skill.

## Things that are writes even though they look like reads

`ReceiveMessage` on SQS hides the message from other consumers for a while, so it is a write. PartiQL (`ExecuteStatement`) can be an `INSERT` or `DELETE`. `Invoke` runs a function. If `call_read` refuses something you expected to be a read, that is why: use `call_write` and tell the user.

## Ask first

- Before anything `destructive`: deletes, purges, `TeardownRecipe` (it removes volumes, so the data).
- Before anything `sensitive`: secret values are off unless `FLOCI_ALLOW_SECRET_VALUES=1`. Never print one back unless the user asked for that value.
- Before `code_write` with a loop: say how many things it will touch.

The code sandbox is a guardrail, not isolation. It is meant for the local emulators; never point it at a real cloud.
