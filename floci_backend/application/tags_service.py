"""Tag management across all AWS resource types via Resource Groups Tagging API."""
import json
from typing import Any, Dict, List, Optional
from floci_backend.infrastructure.aws_cli import AwsCli, AwsCliError


class TagsService:
    def __init__(self, aws_cli: AwsCli):
        self.aws_cli = aws_cli

    async def get_resources(
        self,
        tag_filters: Optional[List[Dict[str, Any]]] = None,
        resource_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """List resources, optionally filtered by tags and/or resource type."""
        args = ["resourcegroupstaggingapi", "get-resources", "--output", "json"]
        if tag_filters:
            filters_json = json.dumps(tag_filters)
            args += ["--tag-filters", filters_json]
        if resource_types:
            args += ["--resource-type-filters"] + resource_types
        try:
            result = await self.aws_cli.run_json(args[:-2])  # run_json appends --output json
            resources = result.get("ResourceTagMappingList", [])
            return {
                "count": len(resources),
                "resources": resources,
            }
        except AwsCliError as e:
            return {"count": 0, "resources": [], "warning": str(e)}

    async def get_tag_keys(self) -> Dict[str, Any]:
        """List all tag keys currently in use across all resources."""
        try:
            result = await self.aws_cli.run_json(["resourcegroupstaggingapi", "get-tag-keys"])
            keys = result.get("TagKeys", [])
            return {"tagKeys": sorted(keys)}
        except AwsCliError as e:
            return {"tagKeys": [], "warning": str(e)}

    async def get_tag_values(self, key: str) -> Dict[str, Any]:
        """List all values used for a given tag key."""
        try:
            result = await self.aws_cli.run_json(
                ["resourcegroupstaggingapi", "get-tag-values", "--key", key]
            )
            values = result.get("TagValues", [])
            return {"key": key, "values": sorted(values)}
        except AwsCliError as e:
            return {"key": key, "values": [], "warning": str(e)}

    async def tag_resources(self, resource_arns: List[str], tags: Dict[str, str]) -> Dict[str, Any]:
        """Apply tags to one or more resources identified by ARN."""
        if not resource_arns:
            raise ValueError("resource_arns must not be empty")
        if not tags:
            raise ValueError("tags must not be empty")

        tags_str = json.dumps(tags)
        arns_str = " ".join(resource_arns)
        try:
            result = await self.aws_cli.run_json(
                [
                    "resourcegroupstaggingapi",
                    "tag-resources",
                    "--resource-arn-list",
                    *resource_arns,
                    "--tags",
                    tags_str,
                ]
            )
            failed = result.get("FailedResourcesMap", {})
            tagged = [arn for arn in resource_arns if arn not in failed]
            return {
                "tagged": tagged,
                "failed": failed,
                "success": len(failed) == 0,
            }
        except AwsCliError as e:
            return {"tagged": [], "failed": {arn: str(e) for arn in resource_arns}, "success": False}

    async def untag_resources(self, resource_arns: List[str], tag_keys: List[str]) -> Dict[str, Any]:
        """Remove specific tag keys from one or more resources."""
        if not resource_arns:
            raise ValueError("resource_arns must not be empty")
        if not tag_keys:
            raise ValueError("tag_keys must not be empty")
        try:
            result = await self.aws_cli.run_json(
                [
                    "resourcegroupstaggingapi",
                    "untag-resources",
                    "--resource-arn-list",
                    *resource_arns,
                    "--tag-keys",
                    *tag_keys,
                ]
            )
            failed = result.get("FailedResourcesMap", {})
            untagged = [arn for arn in resource_arns if arn not in failed]
            return {
                "untagged": untagged,
                "failed": failed,
                "success": len(failed) == 0,
            }
        except AwsCliError as e:
            return {"untagged": [], "failed": {arn: str(e) for arn in resource_arns}, "success": False}
