"""Tag management across all AWS resource types via Resource Groups Tagging API."""
import boto3
from typing import Any, Dict, List, Optional
from floci_backend.config import config


def _client():
    return boto3.client(
        "resourcegroupstaggingapi",
        endpoint_url=config.aws_endpoint_url,
        region_name=config.aws_region,
        aws_access_key_id=config.aws_access_key_id,
        aws_secret_access_key=config.aws_secret_access_key,
    )


class TagsService:
    async def get_resources(
        self,
        tag_filters: Optional[List[Dict[str, Any]]] = None,
        resource_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """List resources, optionally filtered by tags and/or resource type."""
        kwargs: Dict[str, Any] = {}
        if tag_filters:
            kwargs["TagFilters"] = tag_filters
        if resource_types:
            kwargs["ResourceTypeFilters"] = resource_types
        try:
            resources = []
            paginator = _client().get_paginator("get_resources")
            for page in paginator.paginate(**kwargs):
                resources.extend(page.get("ResourceTagMappingList", []))
            return {"count": len(resources), "resources": resources}
        except Exception as e:
            return {"count": 0, "resources": [], "warning": str(e)}

    async def get_tag_keys(self) -> Dict[str, Any]:
        """List all tag keys currently in use across all resources."""
        try:
            keys: List[str] = []
            paginator = _client().get_paginator("get_tag_keys")
            for page in paginator.paginate():
                keys.extend(page.get("TagKeys", []))
            return {"tagKeys": sorted(keys)}
        except Exception as e:
            return {"tagKeys": [], "warning": str(e)}

    async def get_tag_values(self, key: str) -> Dict[str, Any]:
        """List all values used for a given tag key."""
        try:
            values: List[str] = []
            paginator = _client().get_paginator("get_tag_values")
            for page in paginator.paginate(Key=key):
                values.extend(page.get("TagValues", []))
            return {"key": key, "values": sorted(values)}
        except Exception as e:
            return {"key": key, "values": [], "warning": str(e)}

    async def tag_resources(self, resource_arns: List[str], tags: Dict[str, str]) -> Dict[str, Any]:
        """Apply tags to one or more resources identified by ARN."""
        if not resource_arns:
            raise ValueError("resource_arns must not be empty")
        if not tags:
            raise ValueError("tags must not be empty")
        try:
            result = _client().tag_resources(ResourceARNList=resource_arns, Tags=tags)
            failed = result.get("FailedResourcesMap", {})
            tagged = [arn for arn in resource_arns if arn not in failed]
            return {"tagged": tagged, "failed": failed, "success": len(failed) == 0}
        except Exception as e:
            return {"tagged": [], "failed": {arn: str(e) for arn in resource_arns}, "success": False}

    async def untag_resources(self, resource_arns: List[str], tag_keys: List[str]) -> Dict[str, Any]:
        """Remove specific tag keys from one or more resources."""
        if not resource_arns:
            raise ValueError("resource_arns must not be empty")
        if not tag_keys:
            raise ValueError("tag_keys must not be empty")
        try:
            result = _client().untag_resources(ResourceARNList=resource_arns, TagKeys=tag_keys)
            failed = result.get("FailedResourcesMap", {})
            untagged = [arn for arn in resource_arns if arn not in failed]
            return {"untagged": untagged, "failed": failed, "success": len(failed) == 0}
        except Exception as e:
            return {"untagged": [], "failed": {arn: str(e) for arn in resource_arns}, "success": False}
