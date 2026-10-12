"""AWS service models from botocore's bundled JSON."""
from typing import Any

import botocore.session


class BotocoreModels:
    """Implements ports.ServiceModels: every AWS service botocore knows, and its model."""

    def __init__(self) -> None:
        self._session = botocore.session.get_session()

    def services(self) -> list[str]:
        """Every service name botocore ships a model for."""
        return list(self._session.get_available_services())

    def model(self, service: str) -> Any:
        """The botocore ServiceModel of one service."""
        return self._session.get_service_model(service)
