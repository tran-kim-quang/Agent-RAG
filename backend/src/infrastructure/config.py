from functools import lru_cache
from pathlib import Path

import yaml

_CONFIG_PATH = Path(__file__).parents[2] / "configs" / "config.yaml"


@lru_cache(maxsize=1)
def load_config() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as handle:
        return yaml.safe_load(handle)
