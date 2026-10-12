"""Herramientas de gestión de tags (etiquetas) en todos los recursos AWS."""
from tools._client import backend


def register(mcp):

    @mcp.tool()
    async def get_all_tag_keys() -> dict:
        """
        Lists every tag key currently in use across all resources.

        Useful to discover which tags exist before filtering or applying new ones.
        """
        return await backend("GET", "/api/tags/keys")

    @mcp.tool()
    async def get_tag_values(key: str) -> dict:
        """
        Lists every value used for a given tag key.

        Example: get_tag_values('Environment') -> ['dev', 'staging', 'prod']
        """
        return await backend("GET", f"/api/tags/values/{key}")

    @mcp.tool()
    async def find_resources_by_tag(
        tag_key: str,
        tag_value: str | None = None,
        resource_types: list[str] | None = None,
    ) -> dict:
        """
        Finds resources by tag across all AWS services.

        tag_key: tag key to search (e.g. 'Environment', 'Project').
        tag_value: exact value to match. If None, returns every resource that has the key.
        resource_types: AWS resource types to include (e.g. ['s3', 'lambda', 'dynamodb']).
                        If None, all types are searched.

        Example: find_resources_by_tag('Environment', 'prod', ['s3', 'lambda'])
        """
        tag_filter = {"Key": tag_key}
        if tag_value is not None:
            tag_filter["Values"] = [tag_value]
        else:
            tag_filter["Values"] = []

        return await backend("POST", "/api/tags/resources/search", json_data={
            "tagFilters": [tag_filter],
            "resourceTypes": resource_types,
        })

    @mcp.tool()
    async def tag_resources(resource_arns: list[str], tags: dict) -> dict:
        """
        Applies tags to one or more resources identified by ARN.

        resource_arns: list of resource ARNs to tag.
        tags: dictionary of {key: value} to apply.

        Example: tag_resources(
            ['arn:aws:s3:::my-bucket', 'arn:aws:lambda:us-east-1:000000000000:function:my-fn'],
            {'Environment': 'prod', 'Team': 'backend'}
        )
        """
        return await backend("POST", "/api/tags/resources/tag", json_data={
            "resourceArns": resource_arns,
            "tags": tags,
        })

    @mcp.tool()
    async def untag_resources(resource_arns: list[str], tag_keys: list[str]) -> dict:
        """
        Removes specific tags from one or more resources.

        resource_arns: list of resource ARNs.
        tag_keys: list of tag keys to remove.

        Example: untag_resources(['arn:aws:s3:::my-bucket'], ['OldEnvironment', 'Deprecated'])
        """
        return await backend("POST", "/api/tags/resources/untag", json_data={
            "resourceArns": resource_arns,
            "tagKeys": tag_keys,
        })

    @mcp.tool()
    async def list_all_tagged_resources(resource_types: list[str] | None = None) -> dict:
        """
        Lists every resource that has at least one tag.

        resource_types: limits the search to specific resource types.
                        Ex: ['s3', 'lambda:function', 'dynamodb:table', 'sqs:queueurl', 'secretsmanager:secret']
                        If None, all types are returned.

        Returns the ARN, the resource type and all the tags of each resource.
        """
        return await backend("POST", "/api/tags/resources/search", json_data={
            "tagFilters": [],
            "resourceTypes": resource_types,
        })
