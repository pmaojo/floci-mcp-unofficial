"""The generated route catalogs, read from floci_generic/data/*.json."""
import json
import os


class JsonRestData:
    """Implements ports.RestData from a directory of <cloud>.json files."""

    def __init__(self, directory: str) -> None:
        self.directory = directory

    def load(self, cloud: str) -> dict | None:
        """The catalog of one cloud, or None when it was never generated."""
        try:
            with open(os.path.join(self.directory, f"{cloud}.json"), encoding="utf-8") as handle:
                return json.load(handle)
        except FileNotFoundError:
            return None
