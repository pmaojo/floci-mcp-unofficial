"""What is known about each cloud without asking it: names, hints, and the hand-written routes."""

CLOUDS = ("aws", "azure", "gcp", "oci", "recipes")
REST_PROTOCOLS = {"rest-json", "rest-xml"}

# Services Floci lists for each non-AWS cloud (its README). Route shapes follow the provider's
# real REST contract; `verified` marks the ones that answered on a running Floci.
REST_SERVICES = {
    "azure": [
        "blob", "queue", "keyvault", "table", "functions", "appconfiguration", "cosmosdb", "eventhubs",
        "servicebus", "sql", "postgresql", "mysql", "mariadb", "aks", "containerapps", "apim",
        "virtualnetwork", "vm", "redis", "acr", "aci", "eventgrid", "monitor", "email",
        "managedidentity", "policy", "signalr",
    ],
    "gcp": [
        "storage", "pubsub", "secretmanager", "firestore", "datastore", "managedkafka", "eventarc",
        "kms", "iam", "sts", "firebaseauth", "gke", "compute", "cloudrun", "cloudfunctions",
        "cloudtasks", "scheduler", "cloudsql", "bigquery", "logging", "monitoring",
    ],
    "oci": [
        "objectstorage", "identity", "queue", "streaming", "vault", "secrets", "functions", "oke",
    ],
}

# (service, operation, method, path template, summary). {name} in the path comes from params;
# anything else in params goes to the query string (GET) or the JSON body.
HAND_ROUTES = {
    "gcp": [
        ("storage", "ListBuckets", "GET", "/storage/v1/b?project={project}", "Lists Cloud Storage buckets"),
        ("storage", "CreateBucket", "POST", "/storage/v1/b?project={project}", "Creates a bucket; body {name}"),
        ("storage", "ListObjects", "GET", "/storage/v1/b/{bucket}/o", "Lists objects; optional prefix"),
        ("pubsub", "ListTopics", "GET", "/v1/projects/{project}/topics", "Lists Pub/Sub topics"),
        ("pubsub", "CreateTopic", "PUT", "/v1/projects/{project}/topics/{topic}", "Creates a topic"),
        ("secretmanager", "ListSecrets", "GET", "/v1/projects/{project}/secrets", "Lists secret names"),
    ],
    "azure": [
        ("blob", "ListContainers", "GET", "/{account}?comp=list", "Lists blob containers"),
        ("blob", "CreateContainer", "PUT", "/{account}/{container}?restype=container", "Creates a container"),
        ("blob", "DeleteContainer", "DELETE", "/{account}/{container}?restype=container", "Deletes a container and its blobs"),
        ("blob", "ListBlobs", "GET", "/{account}/{container}?restype=container&comp=list", "Lists blobs; optional prefix"),
        ("queue", "ListQueues", "GET", "/{account}-queue?comp=list", "Lists queues"),
        ("queue", "CreateQueue", "PUT", "/{account}-queue/{queue}", "Creates a queue"),
        ("queue", "DeleteQueue", "DELETE", "/{account}-queue/{queue}", "Deletes a queue and its messages"),
        ("table", "ListTables", "GET", "/{account}-table/Tables", "Lists tables"),
        ("keyvault", "ListSecrets", "GET", "/{account}-keyvault/secrets?api-version=7.4", "Lists secret ids"),
    ],
    "oci": [
        ("objectstorage", "GetNamespace", "GET", "/n/", "Returns the Object Storage namespace"),
        ("objectstorage", "ListBuckets", "GET", "/n/{namespace}/b?compartmentId={compartmentId}", "Lists buckets"),
        ("objectstorage", "CreateBucket", "POST", "/n/{namespace}/b", "Creates a bucket; body {name, compartmentId}"),
        ("objectstorage", "ListObjects", "GET", "/n/{namespace}/b/{bucket}/o", "Lists objects; optional prefix"),
        ("objectstorage", "DeleteBucket", "DELETE", "/n/{namespace}/b/{bucket}", "Deletes an empty bucket"),
    ],
}

REST_HINTS = {
    "azure": "Data plane: /{account}[-queue|-keyvault]/... with comp=, restype= query parameters. Responses are XML for Blob and Queue.",
    "gcp": "Google REST: /storage/v1/b/..., /v1/projects/{project}/topics|secrets|... Custom methods use ':verb' suffixes.",
    "oci": "OCI REST: /n/{namespace}/b/... for Object Storage; other services use /20xxxxxx/... with compartmentId.",
}

# Placeholders that have a configured default (see restroute.defaults).
DEFAULTED_PARAMS = {
    "project", "projectId", "projectsId", "projectNumber", "parent", "location", "locationsId", "region", "zone",
    "account", "compartmentId", "namespace", "subscription",
}
