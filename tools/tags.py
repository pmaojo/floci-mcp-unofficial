"""Herramientas de gestión de tags (etiquetas) en todos los recursos AWS."""
from tools._client import backend


def register(mcp):

    @mcp.tool()
    async def get_all_tag_keys() -> dict:
        """
        Lista todas las claves de tag actualmente en uso en todos los recursos.

        Útil para descubrir qué tags existen antes de filtrar o aplicar nuevos.
        """
        return await backend("GET", "/api/tags/keys")

    @mcp.tool()
    async def get_tag_values(key: str) -> dict:
        """
        Lista todos los valores usados para una clave de tag dada.

        Ejemplo: get_tag_values('Environment') → ['dev', 'staging', 'prod']
        """
        return await backend("GET", f"/api/tags/values/{key}")

    @mcp.tool()
    async def find_resources_by_tag(
        tag_key: str,
        tag_value: str | None = None,
        resource_types: list[str] | None = None,
    ) -> dict:
        """
        Busca recursos por tag en todos los servicios AWS.

        tag_key: clave del tag a buscar (ej. 'Environment', 'Project').
        tag_value: valor exacto a filtrar. Si es None, devuelve todos los recursos con esa clave.
        resource_types: lista de tipos de recurso AWS a incluir (ej. ['s3', 'lambda', 'dynamodb']).
                        Si es None, busca en todos los tipos.

        Ejemplo: find_resources_by_tag('Environment', 'prod', ['s3', 'lambda'])
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
        Aplica tags a uno o más recursos identificados por ARN.

        resource_arns: lista de ARNs de los recursos a etiquetar.
        tags: diccionario de {clave: valor} a aplicar.

        Ejemplo: tag_resources(
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
        Elimina tags específicos de uno o más recursos.

        resource_arns: lista de ARNs de los recursos.
        tag_keys: lista de claves de tag a eliminar.

        Ejemplo: untag_resources(
            ['arn:aws:s3:::my-bucket'],
            ['OldEnvironment', 'Deprecated']
        )
        """
        return await backend("POST", "/api/tags/resources/untag", json_data={
            "resourceArns": resource_arns,
            "tagKeys": tag_keys,
        })

    @mcp.tool()
    async def list_all_tagged_resources(resource_types: list[str] | None = None) -> dict:
        """
        Lista todos los recursos que tienen al menos un tag aplicado.

        resource_types: limita la búsqueda a tipos de recurso específicos.
                        Ej: ['s3', 'lambda:function', 'dynamodb:table', 'sqs:queueurl', 'secretsmanager:secret']
                        Si es None, devuelve todos los tipos.

        Devuelve ARN, tipo de recurso y todos los tags de cada recurso.
        """
        return await backend("POST", "/api/tags/resources/search", json_data={
            "tagFilters": [],
            "resourceTypes": resource_types,
        })
