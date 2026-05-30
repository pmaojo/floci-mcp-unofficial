"""Auth routes: AWS CLI profile discovery and STS AssumeRole."""
import configparser
import os
from typing import Optional

import boto3
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from floci_backend.config import config as sidecar_config


class AssumeRoleRequest(BaseModel):
    roleArn: str
    sessionName: str = "floci-session"
    durationSeconds: int = 3600
    externalId: Optional[str] = None


def create_auth_router() -> APIRouter:
    router = APIRouter()

    @router.get("/auth/aws-profiles")
    async def list_aws_profiles():
        """List available profiles from ~/.aws/config and ~/.aws/credentials."""
        profiles: list[dict] = []
        seen: set[str] = set()

        config_path = os.path.expanduser("~/.aws/config")
        if os.path.exists(config_path):
            cp = configparser.ConfigParser()
            cp.read(config_path)
            for section in cp.sections():
                name = "default" if section == "default" else section.removeprefix("profile ").strip()
                if name in seen:
                    continue
                seen.add(name)
                entry: dict = {"name": name, "source": "config"}
                if cp.has_option(section, "region"):
                    entry["region"] = cp.get(section, "region")
                if cp.has_option(section, "sso_start_url"):
                    entry["ssoStartUrl"] = cp.get(section, "sso_start_url")
                    entry["type"] = "sso"
                elif cp.has_option(section, "role_arn"):
                    entry["roleArn"] = cp.get(section, "role_arn")
                    entry["type"] = "assume_role"
                else:
                    entry["type"] = "static"
                profiles.append(entry)

        creds_path = os.path.expanduser("~/.aws/credentials")
        if os.path.exists(creds_path):
            cp2 = configparser.ConfigParser()
            cp2.read(creds_path)
            for section in cp2.sections():
                name = section.strip()
                if name in seen:
                    continue
                seen.add(name)
                entry = {"name": name, "source": "credentials", "type": "static"}
                profiles.append(entry)

        return {"profiles": profiles}

    @router.post("/auth/assume-role")
    async def assume_role(req: AssumeRoleRequest):
        """Call STS AssumeRole and return temporary credentials."""
        try:
            sts = boto3.client(
                "sts",
                endpoint_url=sidecar_config.aws_endpoint_url,
                region_name=sidecar_config.aws_region,
                aws_access_key_id=sidecar_config.aws_access_key_id,
                aws_secret_access_key=sidecar_config.aws_secret_access_key,
            )
            kwargs: dict = {
                "RoleArn": req.roleArn,
                "RoleSessionName": req.sessionName,
                "DurationSeconds": req.durationSeconds,
            }
            if req.externalId:
                kwargs["ExternalId"] = req.externalId

            response = sts.assume_role(**kwargs)
            creds = response["Credentials"]
            return {
                "accessKeyId": creds["AccessKeyId"],
                "secretAccessKey": creds["SecretAccessKey"],
                "sessionToken": creds["SessionToken"],
                "expiration": creds["Expiration"].isoformat(),
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    return router
