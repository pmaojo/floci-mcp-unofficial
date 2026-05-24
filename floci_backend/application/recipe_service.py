import asyncio
import json
import os
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from floci_backend.config import config

class RecipeService:
    def __init__(self):
        self.state_file_path = os.path.join(config.state_dir, 'marketplace-installations.json')
        # Point to the real 'recipes' directory at the root of the project
        self.recipes_dir_path = os.path.abspath(os.path.join(os.getcwd(), 'recipes'))
        self.log_map: Dict[str, List[str]] = {}

    async def list_recipes(self) -> List[Dict[str, Any]]:
        recipes = []
        try:
            for entry in os.scandir(self.recipes_dir_path):
                if entry.is_dir():
                    recipe_json_path = os.path.join(entry.path, 'recipe.json')
                    if os.path.isfile(recipe_json_path):
                        try:
                            with open(recipe_json_path, 'r', encoding='utf-8') as f:
                                recipes.append(json.load(f))
                        except Exception:
                            pass
        except FileNotFoundError:
            pass
        return recipes

    async def get_installations(self) -> Dict[str, Any]:
        try:
            with open(self.state_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    async def get_logs(self, recipe_id: str) -> List[str]:
        return self.log_map.get(recipe_id, [])

    async def _save_installation_state(self, recipe_id: str, inst: Dict[str, Any]) -> None:
        state = await self.get_installations()
        if inst.get('status') == 'IDLE':
            state.pop(recipe_id, None)
        else:
            state[recipe_id] = inst

        os.makedirs(os.path.dirname(self.state_file_path), exist_ok=True)
        with open(self.state_file_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)

    async def install_recipe(self, recipe_id: str, vars: Dict[str, Any]) -> Dict[str, Any]:
        if not recipe_id or not re.match(r'^[a-z0-9-]+$', recipe_id):
            raise ValueError('Invalid recipe ID format')

        recipes = await self.list_recipes()
        recipe = next((r for r in recipes if r.get('id') == recipe_id), None)
        if not recipe:
            raise ValueError(f'Recipe {recipe_id} not found')

        safe_vars = {}
        for v in recipe.get('variables', []):
            val = vars.get(v['key']) if vars and v['key'] in vars else v['default']
            safe_vars[v['key']] = str(val)

        inst = {
            'recipeId': recipe_id,
            'status': 'INSTALLING',
            'vars': safe_vars,
            'error': None
        }

        await self._save_installation_state(recipe_id, inst)
        self.log_map[recipe_id] = [f"[SYSTEM] Starting installation for {recipe.get('name')}..."]

        compose_file = os.path.join(self.recipes_dir_path, recipe_id, 'docker-compose.yml')

        process_vars = os.environ.copy()
        process_vars.update(safe_vars)

        asyncio.create_task(self._run_install_process(recipe_id, compose_file, process_vars, inst))

        return inst

    async def _run_install_process(self, recipe_id: str, compose_file: str, env: Dict[str, str], inst: Dict[str, Any]):
        try:
            process = await asyncio.create_subprocess_exec(
                'docker', 'compose', '-f', compose_file, 'up', '-d',
                env=env,
                cwd=os.path.dirname(compose_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            async def read_stream(stream, is_stderr=False):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded = line.decode().strip()
                    if decoded:
                        self.log_map[recipe_id].append(decoded)

            await asyncio.gather(
                read_stream(process.stdout),
                read_stream(process.stderr, True)
            )

            await process.wait()

            if process.returncode == 0:
                self.log_map[recipe_id].append('[SYSTEM] Docker compose deployment finished successfully!')
                inst['status'] = 'RUNNING'
                inst['installedAt'] = datetime.utcnow().isoformat() + "Z"
            else:
                self.log_map[recipe_id].append(f'[SYSTEM] Installation failed with exit code {process.returncode}')
                inst['status'] = 'FAILED'
                inst['error'] = f'Docker compose exited with code {process.returncode}'

            await self._save_installation_state(recipe_id, inst)

        except Exception as e:
            self.log_map[recipe_id].append(f'[SYSTEM] Exception during installation: {str(e)}')
            inst['status'] = 'FAILED'
            inst['error'] = str(e)
            await self._save_installation_state(recipe_id, inst)


    async def uninstall_recipe(self, recipe_id: str) -> Dict[str, Any]:
        if not recipe_id or not re.match(r'^[a-z0-9-]+$', recipe_id):
            raise ValueError('Invalid recipe ID format')

        recipes = await self.list_recipes()
        if not any(r.get('id') == recipe_id for r in recipes):
            raise ValueError(f'Recipe {recipe_id} not found')

        inst = {
            'recipeId': recipe_id,
            'status': 'UNINSTALLING',
            'error': None
        }

        await self._save_installation_state(recipe_id, inst)
        self.log_map[recipe_id] = [f"[SYSTEM] Stopping and removing containers for {recipe_id}..."]

        compose_file = os.path.join(self.recipes_dir_path, recipe_id, 'docker-compose.yml')

        asyncio.create_task(self._run_uninstall_process(recipe_id, compose_file, os.environ.copy(), inst))

        return inst

    async def _run_uninstall_process(self, recipe_id: str, compose_file: str, env: Dict[str, str], inst: Dict[str, Any]):
        try:
            process = await asyncio.create_subprocess_exec(
                'docker', 'compose', '-f', compose_file, 'down', '-v',
                env=env,
                cwd=os.path.dirname(compose_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            async def read_stream(stream, is_stderr=False):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded = line.decode().strip()
                    if decoded:
                        self.log_map[recipe_id].append(decoded)

            await asyncio.gather(
                read_stream(process.stdout),
                read_stream(process.stderr, True)
            )

            await process.wait()

            if process.returncode == 0:
                self.log_map[recipe_id].append('[SYSTEM] Teardown finished successfully.')
                inst['status'] = 'IDLE'
            else:
                self.log_map[recipe_id].append(f'[SYSTEM] Teardown failed with exit code {process.returncode}')
                inst['status'] = 'FAILED'
                inst['error'] = f'Docker compose down exited with code {process.returncode}'

            await self._save_installation_state(recipe_id, inst)

        except Exception as e:
            self.log_map[recipe_id].append(f'[SYSTEM] Exception during teardown: {str(e)}')
            inst['status'] = 'FAILED'
            inst['error'] = str(e)
            await self._save_installation_state(recipe_id, inst)
