from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any

from floci_backend.application.iac_generator import IacGenerator
from floci_backend.application.data_seeder import DataSeeder
from floci_backend.application.topology_mapper import TopologyMapper
from floci_backend.application.recipe_service import RecipeService
from floci_backend.infrastructure.aws_cli import AwsCli

def create_mcp_extensions_router(
    aws_cli: AwsCli,
    iac_generator: IacGenerator,
    data_seeder: DataSeeder,
    topology_mapper: TopologyMapper,
    recipe_service: RecipeService,
) -> APIRouter:
    router = APIRouter()

    @router.get("/extensions/export-iac")
    async def export_iac(format: str = 'terraform'):
        try:
            if format.lower() == 'terraform':
                code = iac_generator.export_to_terraform()
            elif format.lower() == 'cdk':
                code = iac_generator.export_to_cdk()
            else:
                raise HTTPException(status_code=400, detail="Format must be terraform or cdk")
            return {"format": format, "code": code}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    class AwsCmdRequest(BaseModel):
        command: str

    @router.post("/extensions/run-aws-cmd")
    async def run_aws_cmd(req: AwsCmdRequest):
        import shlex
        args = shlex.split(req.command)
        if not args:
            raise HTTPException(status_code=400, detail="Empty command")
        if args[0] in ['aws', 'awslocal']:
            args = args[1:]
        try:
            result = await aws_cli.run(args)
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    class SeedRequest(BaseModel):
        target: str
        target_name: str
        connection_string: Optional[str] = None
        custom_schema: Optional[Dict[str, Any]] = None

    @router.post("/extensions/seed-data")
    async def seed_data(req: SeedRequest):
        try:
            result = await data_seeder.auto_seed(
                target=req.target,
                target_name=req.target_name,
                connection_string=req.connection_string,
                custom_schema=req.custom_schema
            )
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/extensions/network-topology")
    async def network_topology():
        try:
            diagram = topology_mapper.get_network_topology()
            return {"mermaid": diagram}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/extensions/export-iac-recipes")
    async def export_iac_recipes():
        try:
            installations = await recipe_service.get_installations()
            recipes = await recipe_service.list_recipes()
            code = iac_generator.export_recipes_to_terraform(installations, recipes)
            return {"format": "terraform", "code": code}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return router
