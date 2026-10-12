"""Recipe use cases: list, inspect, deploy and tear down Docker recipes through the RecipeRuntime port."""
import asyncio
from typing import Any

from floci_generic.domain import recipes as domain
from floci_generic.ports import RecipeRuntime


class RecipeService:
    """The operations of the "recipes" cloud. All side effects go through the runtime port."""

    def __init__(self, runtime: RecipeRuntime):
        self.runtime = runtime
        self._native: dict[str, str] | None = None
        self._handlers = {
            "ListRecipes": self._list, "GetRecipe": self._get, "GetStatus": self._status, "GetLogs": self._logs,
            "DeployRecipe": self._deploy, "TeardownRecipe": self._teardown,
        }

    async def call(self, operation: str, params: dict) -> dict:
        """Run one recipe operation. Failures come back as {"error": ...}, never as exceptions."""
        name = domain.resolve(operation)
        if name is None:
            return {"error": f"Unknown recipe operation {operation!r}. Use one of {', '.join(domain.OPERATIONS)}."}
        try:
            return await self._handlers[name](params or {})
        except Exception as exc:  # noqa: BLE001 - the runtime may raise anything (Docker missing, backend down)
            return {"error": f"{type(exc).__name__}: {exc}"[:600]}

    # --------------------------------------------------------------- reads
    async def _native_map(self, recipes: list[dict]) -> dict[str, str]:
        if self._native is None:
            wanted = domain.native_candidates(recipes)
            answering = await asyncio.to_thread(self.runtime.answering_aws, wanted) if wanted else set()
            self._native = domain.native_ids(recipes, answering)
        return self._native

    async def _list(self, params: dict) -> dict:
        recipes = await self.runtime.recipes()
        native = await self._native_map(recipes)
        rows = [domain.summarize(r, native) for r in recipes if domain.matches(r, str(params.get("query", "")).strip())]
        return {"count": len(rows), "recipes": sorted(rows, key=lambda r: r["id"]),
                "hint": "floci_native means Floci emulates the AWS service this recipe stands in for; prefer it unless you need the real engine."}

    async def _find(self, recipe_id: str) -> dict | None:
        return next((r for r in await self.runtime.recipes() if r.get("id") == recipe_id), None)

    async def _get(self, params: dict) -> dict:
        recipe = await self._find(str(params.get("recipe_id", "")))
        if recipe is None:
            return {"error": f"Unknown recipe {params.get('recipe_id')!r}. Use ListRecipes."}
        native = await self._native_map(await self.runtime.recipes())
        keep = ("key", "default", "type", "description")
        return {**domain.summarize(recipe, native), "version": recipe.get("version"), "accessUrl": recipe.get("accessUrl"),
                "variables": [{k: v[k] for k in keep if k in v} for v in recipe.get("variables", [])],
                "aws_parity": (recipe.get("aws") or {}).get("parity")}

    async def _status(self, params: dict) -> dict:
        installed = await self.runtime.installations()
        recipes = {r["id"]: r for r in await self.runtime.recipes()}
        rows = {}
        for rid, inst in installed.items():
            if params.get("recipe_id") and rid != params["recipe_id"]:
                continue
            running = inst.get("status") == "RUNNING"
            rows[rid] = {"status": inst.get("status"), "error": inst.get("error"),
                         "access_url": domain.render_url(recipes.get(rid, {}), inst.get("vars", {})) if running else None}
        return {"installed": rows}

    async def _logs(self, params: dict) -> dict:
        rid = str(params.get("recipe_id", ""))
        if not rid:
            return {"error": "recipe_id is required."}
        lines = await self.runtime.logs(rid)
        return {"recipe_id": rid, "lines": lines[-int(params.get("lines", 40)):]}

    # -------------------------------------------------------------- writes
    async def _wait(self, recipe_id: str, until: set[str], seconds: float) -> dict:
        loop = asyncio.get_event_loop()
        deadline = loop.time() + seconds
        while True:
            inst = (await self.runtime.installations()).get(recipe_id)
            status = inst.get("status") if inst else "IDLE"
            if status in until or loop.time() >= deadline:
                return inst or {"status": "IDLE"}
            await asyncio.sleep(1)

    async def _deploy(self, params: dict) -> dict:
        rid = str(params.get("recipe_id", ""))
        recipe = await self._find(rid)
        if recipe is None:
            return {"error": f"Unknown recipe {rid!r}. Use ListRecipes."}
        plan = domain.plan_deploy(recipe, dict(params.get("vars") or {}), self.runtime.port_busy)
        if plan.error:
            return plan.error
        await self.runtime.install(rid, plan.send)
        final = await self._wait(rid, {"RUNNING", "FAILED"}, float(params.get("wait_seconds", 90)))
        return await self._deploy_result(rid, recipe, plan, final)

    async def _deploy_result(self, rid: str, recipe: dict, plan: Any, final: dict) -> dict:
        defaults = {v["key"]: v.get("default") for v in recipe.get("variables", [])}
        status = final.get("status")
        out: dict[str, Any] = {"recipe_id": rid, "status": status,
                               "access_url": domain.render_url(recipe, {**defaults, **(final.get("vars") or plan.send)})}
        if plan.adjusted:
            out["ports_adjusted"] = plan.adjusted
        if status == "FAILED":
            out["error"] = final.get("error")
            out["log_tail"] = (await self.runtime.logs(rid))[-15:]
        elif status != "RUNNING":
            out["note"] = "Still installing; call GetStatus to follow it."
            out["access_url"] = None
        return out

    async def _teardown(self, params: dict) -> dict:
        rid = str(params.get("recipe_id", ""))
        if await self._find(rid) is None:
            return {"error": f"Unknown recipe {rid!r}. Use ListRecipes."}
        await self.runtime.uninstall(rid)
        final = await self._wait(rid, {"IDLE", "FAILED"}, float(params.get("wait_seconds", 60)))
        out = {"recipe_id": rid, "status": final.get("status")}
        if final.get("status") == "FAILED":
            out["error"] = final.get("error")
        return out
