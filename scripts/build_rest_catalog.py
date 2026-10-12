"""Builds floci_generic/data/{gcp,azure,oci}.json: the route catalog of the three REST clouds.

GCP    generated from Google's public discovery documents (every method of each API).
Azure  the data-plane routes plus the ARM resource types that answer on the running Floci-AZ.
OCI    the eight services Floci-OCI lists, as list/get/create/delete over their collections.

Each operation carries `verified: true` when a read of it answered on the Floci runtime that was
running at build time, `false` when it did not, and no field when it needs arguments we cannot invent.
The result is committed, so nothing needs the network or a running Floci at run time.

    uv run python scripts/build_rest_catalog.py            # all three
    uv run python scripts/build_rest_catalog.py gcp        # one
"""
import json
import os
import re
import sys

import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "floci_generic", "data")

ENDPOINTS = {"gcp": "http://localhost:4588", "azure": "http://localhost:4577", "oci": "http://localhost:4599"}
PROJECT = "floci-local"
SUBSCRIPTION = "00000000-0000-0000-0000-000000000000"
COMPARTMENT = "ocid1.tenancy.oc1..flocilocaltenancy0000000000000000000000000000000000000000"

# discovery api, version, the name Floci uses for the service
GCP_APIS = [
    ("storage", "v1", "storage"), ("pubsub", "v1", "pubsub"), ("secretmanager", "v1", "secretmanager"),
    ("cloudkms", "v1", "kms"), ("firestore", "v1", "firestore"), ("datastore", "v1", "datastore"),
    ("bigquery", "v2", "bigquery"), ("compute", "v1", "compute"), ("sqladmin", "v1beta4", "cloudsql"),
    ("cloudfunctions", "v2", "cloudfunctions"), ("run", "v2", "cloudrun"), ("cloudscheduler", "v1", "scheduler"),
    ("cloudtasks", "v2", "cloudtasks"), ("iam", "v1", "iam"), ("container", "v1", "gke"), ("logging", "v2", "logging"),
    ("monitoring", "v3", "monitoring"), ("eventarc", "v1", "eventarc"), ("managedkafka", "v1", "managedkafka"),
    ("sts", "v1", "sts"),
]
GCP_DEFAULTS = {
    "project": PROJECT, "projectId": PROJECT, "projectsId": PROJECT, "projectNumber": PROJECT,
    "parent": f"projects/{PROJECT}", "location": "us-central1", "locationsId": "us-central1", "region": "us-central1",
    "zone": "us-central1-a", "name": None,
}


# --------------------------------------------------------------------------- GCP
def _singular(word: str) -> str:
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("ses") or word.endswith("xes"):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _camel(word: str) -> str:
    return word[:1].upper() + word[1:]


def friendly(method_id: str) -> str:
    """projects.topics.list -> ListTopics, projects.topics.create -> CreateTopic."""
    parts = method_id.split(".")
    verb, noun = parts[-1], parts[-2] if len(parts) > 1 else ""
    verb_name = {"list": "List", "get": "Get", "create": "Create", "delete": "Delete", "patch": "Update",
                 "update": "Update", "insert": "Create"}.get(verb, _camel(verb))
    noun_name = _camel(noun if verb == "list" else _singular(noun))
    if verb in ("list", "aggregatedList"):
        noun_name = _camel(noun)
    return verb_name + noun_name


def walk(resources: dict, out: list) -> None:
    for resource in resources.values():
        for method in (resource.get("methods") or {}).values():
            out.append(method)
        walk(resource.get("resources") or {}, out)


def build_gcp(client: httpx.Client, base: str | None) -> dict:
    services: dict[str, list] = {}
    for api, version, service in GCP_APIS:
        response = client.get(f"https://www.googleapis.com/discovery/v1/apis/{api}/{version}/rest")
        if response.status_code != 200:
            # Newer APIs publish their own document.
            response = client.get(f"https://{api}.googleapis.com/$discovery/rest", params={"version": version})
        if response.status_code != 200:
            print(f"  gcp {api}: discovery {response.status_code}, skipped")
            continue
        doc = response.json()
        methods: list = []
        walk(doc.get("resources") or {}, methods)
        prefix = doc.get("servicePath", "")
        seen: dict[str, int] = {}
        ops = []
        for m in methods:
            name = friendly(m["id"])
            seen[name] = seen.get(name, 0) + 1
            params = {}
            for pname, p in (m.get("parameters") or {}).items():
                params[pname] = {"in": p.get("location", "query"), "required": bool(p.get("required")),
                                 "type": p.get("type", "string")}
            if m.get("request"):
                params["body"] = {"in": "body", "required": False, "type": m["request"].get("$ref", "object")}
            ops.append({
                "id": m["id"], "name": name, "method": m["httpMethod"], "path": "/" + prefix + m["path"],
                "params": params, "summary": re.sub(r"\s+", " ", m.get("description", ""))[:110],
            })
        # A friendly name used twice is ambiguous: those fall back to the full discovery id.
        for op in ops:
            if seen[op["name"]] > 1:
                op["name"] = op["id"]
        services.setdefault(service, []).extend(ops)
        print(f"  gcp {api} {version}: {len(ops)} operations")
    if base:
        verify_gcp(services, base)
    return services


def _fill_gcp(path: str, params: dict) -> str | None:
    def sub(match):
        key = match.group(2)
        value = GCP_DEFAULTS.get(key, "MISSING")
        return "" if value is None else str(value)

    filled = re.sub(r"\{(\+?)(\w+)\}", sub, path)
    return None if "MISSING" in filled else filled


def verify_gcp(services: dict, base: str) -> None:
    checked = ok = 0
    with httpx.Client(base_url=base, timeout=4) as client:
        for ops in services.values():
            for op in ops:
                if op["method"] != "GET" or "list" not in op["id"].lower():
                    continue
                required = [p for p, v in op["params"].items() if v["in"] == "path"]
                if any(GCP_DEFAULTS.get(p, "MISSING") in ("MISSING", None) for p in required):
                    continue
                url = _fill_gcp(op["path"], op["params"])
                if url is None:
                    continue
                query = {p: GCP_DEFAULTS[p] for p, v in op["params"].items()
                         if v["in"] == "query" and v["required"] and GCP_DEFAULTS.get(p)}
                try:
                    status = client.get(url, params=query, headers={"authorization": "Bearer x"}).status_code
                except httpx.HTTPError:
                    continue
                checked += 1
                op["verified"] = status < 400
                ok += status < 400
    print(f"  gcp verified {ok}/{checked} list operations against {base}")


# ------------------------------------------------------------------------- Azure
ARM_TYPES = [
    # (service, namespace/type, api-version candidates)
    ("storage", "Microsoft.Storage/storageAccounts", ["2021-09-01", "2023-01-01"]),
    ("sql", "Microsoft.Sql/servers", ["2021-11-01", "2022-05-01-preview"]),
    ("redis", "Microsoft.Cache/redis", ["2023-04-01", "2022-06-01"]),
    ("virtualnetwork", "Microsoft.Network/virtualNetworks", ["2023-04-01", "2022-09-01"]),
    ("vm", "Microsoft.Compute/virtualMachines", ["2023-03-01", "2022-11-01"]),
    ("servicebus", "Microsoft.ServiceBus/namespaces", ["2022-10-01-preview", "2021-11-01", "2021-06-01-preview"]),
    ("eventhubs", "Microsoft.EventHub/namespaces", ["2022-10-01-preview", "2021-11-01", "2021-01-01-preview"]),
    ("functions", "Microsoft.Web/sites", ["2022-09-01", "2022-03-01", "2021-02-01"]),
    ("cosmosdb", "Microsoft.DocumentDB/databaseAccounts", ["2023-04-15", "2022-11-15", "2021-10-15"]),
    ("aks", "Microsoft.ContainerService/managedClusters", ["2023-05-01", "2023-01-01", "2022-11-01"]),
    ("containerapps", "Microsoft.App/containerApps", ["2023-05-01", "2022-10-01"]),
    ("apim", "Microsoft.ApiManagement/service", ["2022-08-01", "2021-08-01"]),
    ("acr", "Microsoft.ContainerRegistry/registries", ["2023-01-01-preview", "2022-12-01", "2021-09-01"]),
    ("aci", "Microsoft.ContainerInstance/containerGroups", ["2023-05-01", "2022-09-01", "2021-10-01"]),
    ("eventgrid", "Microsoft.EventGrid/topics", ["2022-06-15", "2021-12-01"]),
    ("monitor", "Microsoft.OperationalInsights/workspaces", ["2022-10-01", "2021-06-01"]),
    ("managedidentity", "Microsoft.ManagedIdentity/userAssignedIdentities", ["2023-01-31", "2018-11-30"]),
    ("policy", "Microsoft.Authorization/policyDefinitions", ["2021-06-01", "2020-09-01"]),
    ("signalr", "Microsoft.SignalRService/signalR", ["2023-02-01", "2022-02-01"]),
    ("postgresql", "Microsoft.DBforPostgreSQL/flexibleServers", ["2022-12-01", "2021-06-01"]),
    ("mysql", "Microsoft.DBforMySQL/flexibleServers", ["2022-12-01", "2021-05-01"]),
    ("mariadb", "Microsoft.DBforMariaDB/servers", ["2018-06-01"]),
    ("appconfiguration", "Microsoft.AppConfiguration/configurationStores", ["2023-03-01", "2022-05-01"]),
    ("email", "Microsoft.Communication/emailServices", ["2023-03-31", "2022-07-01-preview"]),
    ("keyvault", "Microsoft.KeyVault/vaults", ["2022-07-01", "2021-10-01"]),
]


def build_azure(client: httpx.Client, base: str | None) -> dict:
    found = []
    if base:
        with httpx.Client(base_url=base, timeout=4) as live:
            for service, type_, versions in ARM_TYPES:
                for version in versions:
                    try:
                        r = live.get(f"/subscriptions/{SUBSCRIPTION}/providers/{type_}", params={"api-version": version})
                    except httpx.HTTPError:
                        break
                    if r.status_code < 400:
                        found.append({"service": service, "type": type_, "api_version": version})
                        print(f"  azure {type_} @ {version}: answers")
                        break
                else:
                    print(f"  azure {type_}: no api-version answered")
    return {"arm_types": found, "candidates": [t for _, t, _ in ARM_TYPES]}


# --------------------------------------------------------------------------- OCI
OCI_SERVICES = [
    # service, version, collection, singular, needs compartmentId
    ("objectstorage", None, None, None, False),  # namespaced; kept as the hand-written routes
    ("identity", "20160918", "users", "User", True),
    ("identity", "20160918", "compartments", "Compartment", True),
    ("identity", "20160918", "groups", "Group", True),
    ("queue", "20210201", "queues", "Queue", True),
    ("streaming", "20180418", "streams", "Stream", True),
    ("vault", "20180608", "vaults", "Vault", True),
    ("vault", "20180608", "keys", "Key", True),
    ("secrets", "20180608", "secrets", "Secret", True),
    ("functions", "20181201", "applications", "Application", True),
    ("oke", "20180222", "clusters", "Cluster", True),
    ("oke", "20180222", "nodePools", "NodePool", True),
]


def build_oci(client: httpx.Client, base: str | None) -> dict:
    services: dict[str, list] = {}
    live = httpx.Client(base_url=base, timeout=4) if base else None
    for service, version, collection, singular, _ in OCI_SERVICES:
        if version is None:
            continue
        root = f"/{version}/{collection}"
        plural = collection[:1].upper() + collection[1:]
        ops = [
            {"name": f"List{plural}", "method": "GET", "path": root,
             "params": {"compartmentId": {"in": "query", "required": True, "type": "string"}},
             "summary": f"Lists {collection} in a compartment"},
            {"name": f"Get{singular}", "method": "GET", "path": root + "/{id}",
             "params": {"id": {"in": "path", "required": True, "type": "string"}}, "summary": f"Returns one {singular.lower()}"},
            {"name": f"Create{singular}", "method": "POST", "path": root,
             "params": {"body": {"in": "body", "required": True, "type": "object"}}, "summary": f"Creates a {singular.lower()}; body includes compartmentId"},
            {"name": f"Delete{singular}", "method": "DELETE", "path": root + "/{id}",
             "params": {"id": {"in": "path", "required": True, "type": "string"}}, "summary": f"Deletes a {singular.lower()}"},
        ]
        if live is not None:
            try:
                status = live.get(root, params={"compartmentId": COMPARTMENT}).status_code
                ops[0]["verified"] = status < 400
                print(f"  oci {service} {collection}: {status}")
            except httpx.HTTPError:
                pass
        services.setdefault(service, []).extend(ops)
    return services


# --------------------------------------------------------------------------- main
def reachable(url: str) -> bool:
    try:
        httpx.get(url, timeout=2)
        return True
    except httpx.HTTPError:
        return False


def main(argv: list[str]) -> int:
    wanted = argv or ["gcp", "azure", "oci"]
    os.makedirs(DATA, exist_ok=True)
    builders = {"gcp": build_gcp, "azure": build_azure, "oci": build_oci}
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for cloud in wanted:
            base = ENDPOINTS[cloud] if reachable(ENDPOINTS[cloud]) else None
            print(f"{cloud}: {'verifying against ' + base if base else 'runtime not reachable, nothing verified'}")
            data = builders[cloud](client, base)
            path = os.path.join(DATA, f"{cloud}.json")
            with open(path, "w") as handle:
                json.dump(data, handle, separators=(",", ":"), sort_keys=True)
            print(f"  wrote {os.path.relpath(path, ROOT)} ({os.path.getsize(path) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
