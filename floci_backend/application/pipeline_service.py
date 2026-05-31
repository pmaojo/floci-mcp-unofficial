"""
Pipeline service — manage test/demo/production deployments for marketplace recipes.

Local environments (test, demo) run via Docker Compose with project-name isolation
and a port offset so multiple environments can coexist on the same machine.

Production generates AWS Copilot manifests (ECS/Fargate) and Terraform (managed
services), ready to apply with `copilot deploy` or `terraform apply`.
"""

import asyncio
import json
import os
import re
from datetime import datetime
from typing import Dict, Any, List

from floci_backend.config import config

ENVIRONMENTS = ['test', 'demo', 'production']
PORT_OFFSET = {'test': 10000, 'demo': 20000}

# Recipes that run best on ECS/Fargate — no managed AWS equivalent
FARGATE_RECIPES: Dict[str, Dict[str, Any]] = {
    'n8n':                {'image': 'n8nio/n8n:latest',                       'port': 5678,  'type': 'Load Balanced Web Service', 'cpu': 512,  'memory': 1024},
    'metabase':           {'image': 'metabase/metabase:latest',               'port': 3000,  'type': 'Load Balanced Web Service', 'cpu': 1024, 'memory': 2048},
    'temporal':           {'image': 'temporalio/auto-setup:latest',           'port': 8088,  'type': 'Backend Service',           'cpu': 512,  'memory': 1024},
    'uptime-kuma':        {'image': 'louislam/uptime-kuma:1',                 'port': 3001,  'type': 'Load Balanced Web Service', 'cpu': 256,  'memory': 512 },
    'pgadmin':            {'image': 'dpage/pgadmin4:latest',                  'port': 80,    'type': 'Load Balanced Web Service', 'cpu': 256,  'memory': 512 },
    'pocketbase':         {'image': 'ghcr.io/muchobien/pocketbase:latest',    'port': 8090,  'type': 'Load Balanced Web Service', 'cpu': 256,  'memory': 512 },
    'mailpit':            {'image': 'axllent/mailpit:latest',                 'port': 8025,  'type': 'Backend Service',           'cpu': 256,  'memory': 512 },
    'loki':               {'image': 'grafana/loki:2.9.0',                     'port': 3100,  'type': 'Backend Service',           'cpu': 512,  'memory': 1024},
    'jaeger':             {'image': 'jaegertracing/all-in-one:latest',        'port': 16686, 'type': 'Load Balanced Web Service', 'cpu': 256,  'memory': 512 },
    'weaviate':           {'image': 'semitechnologies/weaviate:1.24.0',       'port': 8080,  'type': 'Backend Service',           'cpu': 1024, 'memory': 2048},
    'qdrant':             {'image': 'qdrant/qdrant:latest',                   'port': 6333,  'type': 'Backend Service',           'cpu': 512,  'memory': 1024},
    'meilisearch':        {'image': 'getmeili/meilisearch:latest',            'port': 7700,  'type': 'Backend Service',           'cpu': 256,  'memory': 512 },
    'keycloak':           {'image': 'quay.io/keycloak/keycloak:latest',       'port': 8080,  'type': 'Load Balanced Web Service', 'cpu': 1024, 'memory': 2048},
    'airflow':            {'image': 'apache/airflow:2.9.0',                   'port': 8080,  'type': 'Load Balanced Web Service', 'cpu': 2048, 'memory': 4096},
    'vault':              {'image': 'hashicorp/vault:latest',                 'port': 8200,  'type': 'Backend Service',           'cpu': 256,  'memory': 512 },
    'observability':      {'image': 'grafana/grafana:latest',                 'port': 3001,  'type': 'Backend Service',           'cpu': 512,  'memory': 1024},
    'nginx-proxy-manager':{'image': 'jc21/nginx-proxy-manager:latest',       'port': 81,    'type': 'Load Balanced Web Service', 'cpu': 256,  'memory': 512 },
    'portainer':          {'image': 'portainer/portainer-ce:latest',          'port': 9000,  'type': 'Backend Service',           'cpu': 256,  'memory': 512 },
}


class PipelineService:
    def __init__(self, recipes_dir: str):
        self.recipes_dir = recipes_dir
        self.state_path = os.path.join(config.state_dir, 'pipeline-state.json')
        self.log_map: Dict[str, List[str]] = {}

    # ── State helpers ──────────────────────────────────────────────────────────

    async def _load_state(self) -> Dict[str, Any]:
        try:
            with open(self.state_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {env: {} for env in ENVIRONMENTS}

    async def _save_state(self, state: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        with open(self.state_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)

    def _log_key(self, env: str, recipe_id: str) -> str:
        return f'{env}:{recipe_id}'

    # ── Public API ─────────────────────────────────────────────────────────────

    async def list_environments(self) -> List[Dict[str, Any]]:
        state = await self._load_state()
        result = []
        for env in ENVIRONMENTS:
            deployments = state.get(env, {})
            result.append({
                'name': env,
                'type': 'local' if env != 'production' else 'aws',
                'portOffset': PORT_OFFSET.get(env, 0),
                'deployments': deployments,
            })
        return result

    async def deploy(self, recipe_id: str, env: str, recipe_vars: Dict[str, Any], recipe_meta: Dict[str, Any]) -> Dict[str, Any]:
        if env not in ENVIRONMENTS:
            raise ValueError(f'Unknown environment: {env}. Must be one of {ENVIRONMENTS}')
        if env == 'production':
            raise ValueError('Production environment does not support local deployment. Use generate_manifests() instead.')

        offset = PORT_OFFSET.get(env, 0)
        safe_vars: Dict[str, str] = {}
        for v in recipe_meta.get('variables', []):
            key = v['key']
            raw = recipe_vars.get(key, v['default'])
            if v['type'] == 'number' and offset:
                try:
                    raw = int(raw) + offset
                except (TypeError, ValueError):
                    pass
            safe_vars[key] = str(raw)

        project_name = f'floci-{env}-{recipe_id}'
        inst: Dict[str, Any] = {
            'recipeId': recipe_id,
            'env': env,
            'status': 'INSTALLING',
            'vars': safe_vars,
            'projectName': project_name,
            'error': None,
        }

        state = await self._load_state()
        state.setdefault(env, {})[recipe_id] = inst
        await self._save_state(state)

        log_key = self._log_key(env, recipe_id)
        self.log_map[log_key] = [f'[SYSTEM] Deploying {recipe_id} to {env} (project={project_name})...']

        compose_file = os.path.join(self.recipes_dir, recipe_id, 'docker-compose.yml')
        process_env = {**os.environ, **safe_vars, 'COMPOSE_PROJECT_NAME': project_name}
        asyncio.create_task(self._run_compose_up(recipe_id, env, compose_file, process_env, inst))
        return inst

    async def teardown(self, recipe_id: str, env: str) -> Dict[str, Any]:
        if env not in ENVIRONMENTS:
            raise ValueError(f'Unknown environment: {env}')
        if env == 'production':
            raise ValueError('Production teardown is not supported from the UI — run terraform destroy manually.')

        state = await self._load_state()
        inst = state.get(env, {}).get(recipe_id, {})
        project_name = inst.get('projectName', f'floci-{env}-{recipe_id}')

        inst = {**inst, 'status': 'UNINSTALLING', 'error': None}
        state.setdefault(env, {})[recipe_id] = inst
        await self._save_state(state)

        log_key = self._log_key(env, recipe_id)
        self.log_map[log_key] = [f'[SYSTEM] Tearing down {recipe_id} in {env}...']

        compose_file = os.path.join(self.recipes_dir, recipe_id, 'docker-compose.yml')
        process_env = {**os.environ, 'COMPOSE_PROJECT_NAME': project_name}
        asyncio.create_task(self._run_compose_down(recipe_id, env, compose_file, process_env, inst))
        return inst

    async def promote(self, recipe_id: str, from_env: str, to_env: str, recipe_meta: Dict[str, Any]) -> Dict[str, Any]:
        """Copy a deployment from one local env to the next (test → demo)."""
        if to_env == 'production':
            raise ValueError('To promote to production, use generate_manifests() and apply with Copilot or Terraform.')

        state = await self._load_state()
        source = state.get(from_env, {}).get(recipe_id)
        if not source or source.get('status') != 'RUNNING':
            raise ValueError(f'{recipe_id} is not RUNNING in {from_env}')

        # Re-derive vars without the from_env port offset, then apply to_env offset
        from_offset = PORT_OFFSET.get(from_env, 0)
        to_offset = PORT_OFFSET.get(to_env, 0)
        base_vars: Dict[str, str] = {}
        for v in recipe_meta.get('variables', []):
            key = v['key']
            raw = source['vars'].get(key, str(v['default']))
            if v['type'] == 'number' and from_offset:
                try:
                    raw = str(int(raw) - from_offset)
                except (TypeError, ValueError):
                    pass
            base_vars[key] = raw

        return await self.deploy(recipe_id, to_env, base_vars, recipe_meta)

    async def get_logs(self, recipe_id: str, env: str) -> List[str]:
        return self.log_map.get(self._log_key(env, recipe_id), [])

    def generate_copilot_manifests(self, recipe_id: str, recipe_meta: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate AWS Copilot manifest files for an ECS/Fargate deployment.
        Returns a dict of {relative_path: file_content}.
        """
        fargate = FARGATE_RECIPES.get(recipe_id)
        if not fargate:
            return {}

        name = recipe_id
        svc_type = fargate['type']
        image = fargate['image']
        port = fargate['port']
        cpu = fargate['cpu']
        memory = fargate['memory']
        prod_cpu = min(cpu * 2, 4096)
        prod_mem = min(memory * 2, 8192)

        health_path = '/health' if svc_type == 'Load Balanced Web Service' else ''
        http_block = (
            f'\nhttp:\n  path: \'/\'\n  healthcheck: \'{health_path}\'\n'
            if svc_type == 'Load Balanced Web Service' else ''
        )

        svc_manifest = f"""\
# Generated by Floci Studio Pipeline
# Apply with: copilot svc deploy --name {name} --env <environment>

name: {name}
type: {svc_type}

image:
  location: {image}
  port: {port}

cpu: {cpu}
memory: {memory}
count: 1
{http_block}
environments:
  test:
    count: 1
    cpu: {cpu}
    memory: {memory}
  demo:
    count: 1
    cpu: {cpu}
    memory: {memory}
  production:
    count: 2
    cpu: {prod_cpu}
    memory: {prod_mem}
"""

        env_manifest_tpl = """\
# Generated by Floci Studio Pipeline
# Apply with: copilot env deploy --name {env}

name: {env}
type: Environment
"""

        manifests = {
            f'copilot/services/{name}/manifest.yml': svc_manifest,
        }
        for env in ENVIRONMENTS:
            manifests[f'copilot/environments/{env}/manifest.yml'] = env_manifest_tpl.format(env=env)

        return manifests

    # ── Docker Compose helpers ─────────────────────────────────────────────────

    async def _run_compose_up(self, recipe_id: str, env: str, compose_file: str, process_env: Dict[str, str], inst: Dict[str, Any]):
        log_key = self._log_key(env, recipe_id)
        try:
            process = await asyncio.create_subprocess_exec(
                'docker', 'compose', '-f', compose_file, 'up', '-d',
                env=process_env, cwd=os.path.dirname(compose_file),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await self._stream_logs(process, log_key)
            await process.wait()

            if process.returncode == 0:
                self.log_map[log_key].append('[SYSTEM] Deployment finished successfully.')
                inst['status'] = 'RUNNING'
                inst['deployedAt'] = datetime.utcnow().isoformat() + 'Z'
            else:
                inst['status'] = 'FAILED'
                inst['error'] = f'docker compose up exited with code {process.returncode}'
                self.log_map[log_key].append(f'[SYSTEM] {inst["error"]}')
        except Exception as e:
            inst['status'] = 'FAILED'
            inst['error'] = str(e)
            self.log_map[log_key].append(f'[SYSTEM] Exception: {e}')

        state = await self._load_state()
        state.setdefault(env, {})[recipe_id] = inst
        await self._save_state(state)

    async def _run_compose_down(self, recipe_id: str, env: str, compose_file: str, process_env: Dict[str, str], inst: Dict[str, Any]):
        log_key = self._log_key(env, recipe_id)
        try:
            process = await asyncio.create_subprocess_exec(
                'docker', 'compose', '-f', compose_file, 'down', '-v',
                env=process_env, cwd=os.path.dirname(compose_file),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            await self._stream_logs(process, log_key)
            await process.wait()

            if process.returncode == 0:
                self.log_map[log_key].append('[SYSTEM] Teardown complete.')
                inst['status'] = 'IDLE'
            else:
                inst['status'] = 'FAILED'
                inst['error'] = f'docker compose down exited with code {process.returncode}'
        except Exception as e:
            inst['status'] = 'FAILED'
            inst['error'] = str(e)

        state = await self._load_state()
        env_state = state.get(env, {})
        if inst.get('status') == 'IDLE':
            env_state.pop(recipe_id, None)
        else:
            env_state[recipe_id] = inst
        state[env] = env_state
        await self._save_state(state)

    async def _stream_logs(self, process: asyncio.subprocess.Process, log_key: str):
        async def read(stream):
            while True:
                line = await stream.readline()
                if not line:
                    break
                decoded = line.decode().strip()
                if decoded:
                    self.log_map.setdefault(log_key, []).append(decoded)

        await asyncio.gather(read(process.stdout), read(process.stderr))
