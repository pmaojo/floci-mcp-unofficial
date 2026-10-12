"""Tag management across all AWS resource types via Resource Groups Tagging API."""
from typing import Any, Dict, List, Optional

from floci_backend.application.ports import ResourceTagging


class TagsService:
    def __init__(self, tagging: ResourceTagging):
        self._tagging = tagging

    async def get_resources(
        self,
        tag_filters: Optional[List[Dict[str, Any]]] = None,
        resource_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """List resources, optionally filtered by tags and/or resource type."""
        try:
            resources = self._tagging.resources(tag_filters, resource_types)
            return {"count": len(resources), "resources": resources}
        except Exception as e:
            return {"count": 0, "resources": [], "warning": str(e)}

    async def get_tag_keys(self) -> Dict[str, Any]:
        """List all tag keys currently in use across all resources."""
        try:
            return {"tagKeys": sorted(self._tagging.tag_keys())}
        except Exception as e:
            return {"tagKeys": [], "warning": str(e)}

    async def get_tag_values(self, key: str) -> Dict[str, Any]:
        """List all values used for a given tag key."""
        try:
            return {"key": key, "values": sorted(self._tagging.tag_values(key))}
        except Exception as e:
            return {"key": key, "values": [], "warning": str(e)}

    async def tag_resources(self, resource_arns: List[str], tags: Dict[str, str]) -> Dict[str, Any]:
        """Apply tags to one or more resources identified by ARN."""
        if not resource_arns:
            raise ValueError("resource_arns must not be empty")
        if not tags:
            raise ValueError("tags must not be empty")
        try:
            failed = self._tagging.tag(resource_arns, tags)
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
            failed = self._tagging.untag(resource_arns, tag_keys)
            untagged = [arn for arn in resource_arns if arn not in failed]
            return {"untagged": untagged, "failed": failed, "success": len(failed) == 0}
        except Exception as e:
            return {"untagged": [], "failed": {arn: str(e) for arn in resource_arns}, "success": False}
