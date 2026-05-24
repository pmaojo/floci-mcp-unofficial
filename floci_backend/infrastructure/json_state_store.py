import json
import os
import aiofiles
from typing import TypeVar, Generic
from pydantic import BaseModel
from floci_backend.config import config

T = TypeVar('T', bound=BaseModel)

class JsonStateStore(Generic[T]):
    def __init__(self, file_name: str, initial_state_cls: type[T], initial_state_dict: dict):
        self.file_name = file_name
        self.initial_state_cls = initial_state_cls
        self.initial_state_dict = initial_state_dict

    async def read(self) -> T:
        await self._ensure_directory()
        try:
            async with aiofiles.open(self._file_path(), 'r') as f:
                content = await f.read()
            data = {**self.initial_state_dict, **json.loads(content)}
            return self.initial_state_cls(**data)
        except FileNotFoundError:
            initial_state = self.initial_state_cls(**self.initial_state_dict)
            await self.write(initial_state)
            return initial_state

    async def write(self, state: T):
        await self._ensure_directory()
        async with aiofiles.open(self._file_path(), 'w') as f:
            await f.write(state.model_dump_json(indent=2) + '\n')

    async def update(self, mutator) -> T:
        current = await self.read()
        next_state = mutator(current) or current
        await self.write(next_state)
        return next_state

    async def _ensure_directory(self):
        os.makedirs(config.state_dir, exist_ok=True)

    def _file_path(self) -> str:
        return os.path.join(config.state_dir, self.file_name)
