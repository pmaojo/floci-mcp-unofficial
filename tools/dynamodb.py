"""Herramientas DynamoDB: tablas, ítems, queries y scans."""
from tools._client import clean, make_client


def register(mcp):

    @mcp.tool()
    async def list_dynamodb_tables() -> dict:
        """Lista todas las tablas DynamoDB del entorno."""
        r = make_client("dynamodb").list_tables()
        return {"tables": r.get("TableNames", [])}

    @mcp.tool()
    async def create_dynamodb_table(
        name: str,
        partition_key: str,
        partition_key_type: str = "S",
        sort_key: str | None = None,
        sort_key_type: str = "S",
        billing_mode: str = "PAY_PER_REQUEST",
    ) -> dict:
        """
        Crea una tabla DynamoDB.

        partition_key_type / sort_key_type: 'S' (String), 'N' (Number), 'B' (Binary).
        billing_mode: 'PAY_PER_REQUEST' (serverless) o 'PROVISIONED'.
        """
        attr_defs = [{"AttributeName": partition_key, "AttributeType": partition_key_type}]
        key_schema = [{"AttributeName": partition_key, "KeyType": "HASH"}]
        if sort_key:
            attr_defs.append({"AttributeName": sort_key, "AttributeType": sort_key_type})
            key_schema.append({"AttributeName": sort_key, "KeyType": "RANGE"})
        params: dict = {
            "TableName": name,
            "AttributeDefinitions": attr_defs,
            "KeySchema": key_schema,
            "BillingMode": billing_mode,
        }
        if billing_mode == "PROVISIONED":
            params["ProvisionedThroughput"] = {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
        r = make_client("dynamodb").create_table(**params)
        return clean({"table": name, "status": r["TableDescription"]["TableStatus"]})

    @mcp.tool()
    async def delete_dynamodb_table(name: str) -> dict:
        """Elimina una tabla DynamoDB y todos sus datos de forma permanente."""
        make_client("dynamodb").delete_table(TableName=name)
        return {"deleted": name}

    @mcp.tool()
    async def put_dynamodb_item(table: str, item: dict) -> dict:
        """
        Inserta o reemplaza un ítem en una tabla DynamoDB.

        El ítem debe usar el formato de tipos DynamoDB:
        {'pk': {'S': 'valor'}, 'contador': {'N': '42'}, 'activo': {'BOOL': True}}.
        """
        make_client("dynamodb").put_item(TableName=table, Item=item)
        return {"table": table, "inserted": True}

    @mcp.tool()
    async def get_dynamodb_item(table: str, key: dict) -> dict:
        """
        Obtiene un ítem de DynamoDB por su clave primaria.

        key en formato DynamoDB: {'pk': {'S': 'valor'}} o {'pk': {'S': 'v'}, 'sk': {'N': '1'}}.
        """
        r = make_client("dynamodb").get_item(TableName=table, Key=key)
        return clean({"item": r.get("Item")})

    @mcp.tool()
    async def query_dynamodb(
        table: str,
        key_condition_expression: str,
        expression_attribute_values: dict,
        filter_expression: str | None = None,
        limit: int | None = None,
        scan_index_forward: bool = True,
    ) -> dict:
        """
        Consulta ítems en DynamoDB por clave de partición.

        Ejemplo:
          key_condition_expression = 'user_id = :uid'
          expression_attribute_values = {':uid': {'S': 'user-123'}}
        scan_index_forward=false ordena descendentemente por sort key.
        """
        params: dict = {
            "TableName": table,
            "KeyConditionExpression": key_condition_expression,
            "ExpressionAttributeValues": expression_attribute_values,
            "ScanIndexForward": scan_index_forward,
        }
        if filter_expression:
            params["FilterExpression"] = filter_expression
        if limit:
            params["Limit"] = limit
        r = make_client("dynamodb").query(**params)
        return clean({"count": r.get("Count", 0), "items": r.get("Items", [])})

    @mcp.tool()
    async def scan_dynamodb(
        table: str,
        filter_expression: str | None = None,
        expression_attribute_values: dict | None = None,
        limit: int | None = None,
    ) -> dict:
        """
        Escanea todos los ítems de una tabla DynamoDB.

        Para tablas grandes, preferir query_dynamodb. filter_expression se aplica
        tras el scan (no reduce el coste de lectura).
        """
        params: dict = {"TableName": table}
        if filter_expression:
            params["FilterExpression"] = filter_expression
        if expression_attribute_values:
            params["ExpressionAttributeValues"] = expression_attribute_values
        if limit:
            params["Limit"] = limit
        r = make_client("dynamodb").scan(**params)
        return clean({"count": r.get("Count", 0), "items": r.get("Items", [])})

    @mcp.tool()
    async def delete_dynamodb_item(table: str, key: dict) -> dict:
        """
        Elimina un ítem de DynamoDB por su clave primaria.

        key en formato DynamoDB: {'pk': {'S': 'valor'}}.
        """
        make_client("dynamodb").delete_item(TableName=table, Key=key)
        return {"deleted": True}
