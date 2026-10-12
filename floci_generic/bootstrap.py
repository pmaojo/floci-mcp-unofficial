"""Composition root: the only module that knows both the application and its adapters.

Importing it configures the catalog with the real service models and route data, and exposes the
Gateway and make_pair that the tools, the eval and the tests use. Everything else in the package
depends on ports, so a different adapter (a fake in a test, another SDK) is a change here and nowhere else.
"""
import os
from typing import Mapping

from floci_generic.adapters.boto_transport import BotoAwsTransport
from floci_generic.adapters.botocore_models import BotocoreModels
from floci_generic.adapters.http_transport import HttpxRestTransport
from floci_generic.adapters.recipe_runtime import InProcessRecipeRuntime
from floci_generic.adapters.rest_data import JsonRestData
from floci_generic.app import catalog
from floci_generic.app.admission import Admission
from floci_generic.app import gateway as gateway_app
from floci_generic.app.probe import probe_aws
from floci_generic.app.recipes import RecipeService
from floci_generic.domain.errors import Blocked  # noqa: F401  re-exported
from floci_generic.domain.policy import Policy

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_TRUTHY = ("1", "true", "yes", "on")

models = BotocoreModels()
catalog.configure(models, JsonRestData(DATA_DIR))
aws = BotoAwsTransport(models)
rest = HttpxRestTransport()


def _answering(services: list[str]) -> set[str]:
    results = probe_aws(Gateway(), services)
    return {name for name, state in results.items() if state == "answers"}


recipe_service = RecipeService(InProcessRecipeRuntime(_answering))


class Gateway(gateway_app.Gateway):
    """The application gateway wired to the real adapters. Arguments are the policy; any adapter can be replaced."""

    def __init__(self, allow_write: bool = False, dry_run_writes: bool = False, allow_sensitive: bool | None = None,
                 *, aws_transport=None, rest_transport=None, recipes: RecipeService | None = None,
                 env: Mapping[str, str] | None = None):
        environment = env if env is not None else os.environ
        if allow_sensitive is None:
            allow_sensitive = environment.get("FLOCI_ALLOW_SECRET_VALUES", "").lower() in _TRUTHY
        policy = Policy(allow_write=allow_write, dry_run_writes=dry_run_writes, allow_sensitive=allow_sensitive)
        transport = aws_transport or aws
        super().__init__(transport, rest_transport or rest, Admission(policy, transport.validate),
                         recipes or recipe_service, environment)


def make_pair() -> "tuple[Gateway, Gateway]":
    """The reading and the writing gateway a toolset registers. The eval replaces this to record dry runs."""
    return Gateway(allow_write=False), Gateway(allow_write=True)


def probe(services: list[str] | None = None) -> dict[str, str]:
    """Which AWS services answer on the running Floci (every service when none are named)."""
    return probe_aws(Gateway(), services)
