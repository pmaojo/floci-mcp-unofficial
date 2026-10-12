"""boto3 adapter for the ResourceTagging port."""
from typing import Any, Dict, List, Optional

from floci_backend.infrastructure.boto_factory import make_client


class BotoResourceTagging:
    """Builds the client on each call, so a configuration problem surfaces as the service's warning, not at import."""

    def resources(
        self, tag_filters: Optional[List[Dict[str, Any]]] = None, resource_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        kwargs: Dict[str, Any] = {}
        if tag_filters:
            kwargs["TagFilters"] = tag_filters
        if resource_types:
            kwargs["ResourceTypeFilters"] = resource_types
        found: List[Dict[str, Any]] = []
        for page in make_client("resourcegroupstaggingapi").get_paginator("get_resources").paginate(**kwargs):
            found.extend(page.get("ResourceTagMappingList", []))
        return found

    def tag_keys(self) -> List[str]:
        keys: List[str] = []
        for page in make_client("resourcegroupstaggingapi").get_paginator("get_tag_keys").paginate():
            keys.extend(page.get("TagKeys", []))
        return keys

    def tag_values(self, key: str) -> List[str]:
        values: List[str] = []
        for page in make_client("resourcegroupstaggingapi").get_paginator("get_tag_values").paginate(Key=key):
            values.extend(page.get("TagValues", []))
        return values

    def tag(self, resource_arns: List[str], tags: Dict[str, str]) -> Dict[str, Any]:
        result = make_client("resourcegroupstaggingapi").tag_resources(ResourceARNList=resource_arns, Tags=tags)
        return result.get("FailedResourcesMap", {})

    def untag(self, resource_arns: List[str], tag_keys: List[str]) -> Dict[str, Any]:
        result = make_client("resourcegroupstaggingapi").untag_resources(ResourceARNList=resource_arns, TagKeys=tag_keys)
        return result.get("FailedResourcesMap", {})
