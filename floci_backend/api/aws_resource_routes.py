from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional

from floci_backend.application.aws_resource_service import AwsResourceService
from floci_backend.application.compatibility_service import CompatibilityService

def create_aws_resource_router(aws_resource_service: AwsResourceService, compatibility_service: CompatibilityService) -> APIRouter:
    router = APIRouter()

    @router.get('/aws-services')
    async def get_aws_services() -> Dict[str, Any]:
        return {'services': aws_resource_service.list_services()}

    @router.get('/aws-services/{service_key}/overview')
    async def get_overview(service_key: str) -> Dict[str, Any]:
        try:
            return await aws_resource_service.get_overview(service_key)
        except Exception as error:
            status_code = getattr(error, 'status_code', 500)
            if 'Unknown AWS service' in str(error):
                status_code = 404
            raise HTTPException(status_code=status_code, detail=str(error) or 'Failed to read AWS service overview')

    @router.post('/aws-services/codeartifact/domains')
    async def create_codeartifact_domain(request: Dict[str, Any] = {}) -> Dict[str, Any]:
        try:
            return await compatibility_service.create_code_artifact_domain(str(request.get('name', '')))
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error) or 'Failed to create CodeArtifact domain')

    @router.post('/aws-services/codeartifact/repositories')
    async def create_codeartifact_repository(request: Dict[str, Any] = {}) -> Dict[str, Any]:
        try:
            return await compatibility_service.create_code_artifact_repository(
                str(request.get('domainName', '')),
                str(request.get('repositoryName', ''))
            )
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error) or 'Failed to create CodeArtifact repository')

    @router.delete('/aws-services/codeartifact/repositories/{domain_name}/{repository_name}')
    async def delete_codeartifact_repository(domain_name: str, repository_name: str) -> Dict[str, Any]:
        try:
            return await compatibility_service.delete_code_artifact_repository(domain_name, repository_name)
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error) or 'Failed to delete CodeArtifact repository')

    @router.post('/aws-services/{service_key}/resources/{resource_id}')
    async def create_generic_resource(service_key: str, resource_id: str, request: Dict[str, Any] = {}) -> Dict[str, Any]:
        try:
            return await compatibility_service.create_generic_resource(
                service_key, resource_id, str(request.get('name', ''))
            )
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error) or 'Failed to create compatibility resource')

    @router.delete('/aws-services/{service_key}/resources/{resource_id}/{name}')
    async def delete_generic_resource(service_key: str, resource_id: str, name: str) -> Dict[str, Any]:
        try:
            return await compatibility_service.delete_generic_resource(service_key, resource_id, name)
        except Exception as error:
            raise HTTPException(status_code=400, detail=str(error) or 'Failed to delete compatibility resource')

    return router
