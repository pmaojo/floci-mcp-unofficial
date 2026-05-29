"""Herramientas Step Functions: state machines y ejecuciones."""
import json
from tools._client import clean, make_client


def register(mcp):

    @mcp.tool()
    async def list_step_functions() -> dict:
        """Lista todas las state machines de AWS Step Functions del entorno."""
        r = make_client("stepfunctions").list_state_machines()
        return clean({"state_machines": r.get("stateMachines", [])})

    @mcp.tool()
    async def start_sfn_execution(
        state_machine_arn: str,
        input: dict | None = None,
        name: str | None = None,
    ) -> dict:
        """
        Inicia una ejecución de una state machine de Step Functions.

        input es el payload JSON que recibirá el primer estado.
        name es un identificador único para la ejecución (opcional, se genera automáticamente).
        """
        params: dict = {
            "stateMachineArn": state_machine_arn,
            "input": json.dumps(input or {}),
        }
        if name:
            params["name"] = name
        r = make_client("stepfunctions").start_execution(**params)
        return clean({"execution_arn": r["executionArn"], "start_date": r["startDate"]})

    @mcp.tool()
    async def describe_sfn_execution(execution_arn: str) -> dict:
        """
        Obtiene el estado completo de una ejecución de Step Functions.

        Devuelve: status (RUNNING/SUCCEEDED/FAILED/TIMED_OUT/ABORTED),
        input, output y tiempos de inicio y fin.
        """
        r = make_client("stepfunctions").describe_execution(executionArn=execution_arn)
        return clean({
            "execution_arn": r["executionArn"],
            "status": r["status"],
            "start_date": r["startDate"],
            "stop_date": r.get("stopDate"),
            "input": r.get("input"),
            "output": r.get("output"),
        })

    @mcp.tool()
    async def list_sfn_executions(
        state_machine_arn: str,
        status_filter: str | None = None,
        max_results: int = 20,
    ) -> dict:
        """
        Lista las ejecuciones de una state machine.

        status_filter: 'RUNNING', 'SUCCEEDED', 'FAILED', 'TIMED_OUT' o 'ABORTED'.
        """
        params: dict = {"stateMachineArn": state_machine_arn, "maxResults": max_results}
        if status_filter:
            params["statusFilter"] = status_filter
        r = make_client("stepfunctions").list_executions(**params)
        return clean({"executions": r.get("executions", [])})
