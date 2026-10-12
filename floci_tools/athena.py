"""Herramientas Athena: consultas SQL y catálogo Glue."""
import asyncio
import time

from floci_tools._client import backend, clean, make_client


def register(mcp):

    @mcp.tool()
    async def list_glue_databases() -> dict:
        """Lists the databases and tables of the AWS Glue data catalogue (used by Athena)."""
        return await backend("GET", "/api/athena/catalog")

    @mcp.tool()
    async def run_athena_query(
        sql: str,
        database: str = "default",
        workgroup: str = "primary",
        timeout_seconds: int = 60,
        max_rows: int = 100,
    ) -> dict:
        """
        Runs a SQL query on Athena (the real Athena API of Floci, backed by floci-duck) and waits for the result.

        The first query can take a few seconds while the DuckDB container starts.
        Returns columns and rows (up to max_rows), or the status and reason if it fails or times out.
        """
        athena = make_client("athena")

        def start():
            return athena.start_query_execution(
                QueryString=sql,
                QueryExecutionContext={"Database": database},
                WorkGroup=workgroup,
            )["QueryExecutionId"]

        execution_id = await asyncio.to_thread(start)
        deadline = time.monotonic() + timeout_seconds
        status: dict = {}
        while time.monotonic() < deadline:
            execution = await asyncio.to_thread(
                lambda: athena.get_query_execution(QueryExecutionId=execution_id)["QueryExecution"]
            )
            status = execution["Status"]
            if status["State"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
                break
            await asyncio.sleep(1)

        state = status.get("State", "UNKNOWN")
        if state != "SUCCEEDED":
            return clean({
                "execution_id": execution_id,
                "status": state if state != "RUNNING" and state != "QUEUED" else "TIMEOUT",
                "reason": status.get("StateChangeReason"),
            })

        def fetch():
            rows: list[list] = []
            columns: list[dict] = []
            token = None
            while len(rows) < max_rows + 1:
                kwargs = {"QueryExecutionId": execution_id, "MaxResults": min(1000, max_rows + 1)}
                if token:
                    kwargs["NextToken"] = token
                page = athena.get_query_results(**kwargs)
                if not columns:
                    info = page["ResultSet"]["ResultSetMetadata"]["ColumnInfo"]
                    columns = [{"name": c["Name"], "type": c["Type"]} for c in info]
                for row in page["ResultSet"]["Rows"]:
                    rows.append([cell.get("VarCharValue") for cell in row.get("Data", [])])
                token = page.get("NextToken")
                if not token:
                    break
            return columns, rows

        columns, rows = await asyncio.to_thread(fetch)
        # Athena returns the header as the first row of the first page.
        if rows and [c["name"] for c in columns] == rows[0]:
            rows = rows[1:]
        return {
            "execution_id": execution_id,
            "status": "SUCCEEDED",
            "columns": columns,
            "rows": rows[:max_rows],
            "truncated": len(rows) > max_rows,
        }

    @mcp.tool()
    async def get_athena_query_history(max_results: int = 20) -> dict:
        """Lists the latest Athena queries of the emulator with their status and SQL."""
        athena = make_client("athena")

        def fetch():
            ids = athena.list_query_executions(MaxResults=min(max_results, 50)).get("QueryExecutionIds", [])
            if not ids:
                return []
            queries = []
            for execution_id in ids:
                q = athena.get_query_execution(QueryExecutionId=execution_id)["QueryExecution"]
                queries.append({
                    "execution_id": q["QueryExecutionId"],
                    "query": q.get("Query"),
                    "database": q.get("QueryExecutionContext", {}).get("Database"),
                    "status": q.get("Status", {}).get("State"),
                    "submitted_at": q.get("Status", {}).get("SubmissionDateTime"),
                })
            return queries

        return clean({"queries": await asyncio.to_thread(fetch)})
