"""Policy loader.

Tolerances, thresholds, weights and source sigmas live in YAML (see rules 6 in the
master prompt) so they can be calibrated without a code change. Everything marked
[P] in docs/backend.md is a starting heuristic and must stay configurable here.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


class PolicyError(RuntimeError):
    """Raised when a policy file is missing or malformed."""


@dataclass(frozen=True)
class PolicyBundle:
    path: str
    name: str
    version: str
    data: dict[str, Any]


def load_policy(path: str | Path) -> PolicyBundle:
    policy_path = Path(path)
    if not policy_path.is_file():
        raise PolicyError(f"policy file not found: {policy_path}")
    try:
        raw = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PolicyError(f"policy file is not valid YAML: {policy_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise PolicyError(f"policy file must contain a mapping at the top level: {policy_path}")

    # Identity lives under a `policy:` block; tolerate a flat file as well.
    meta = raw.get("policy", raw)
    if not isinstance(meta, dict):
        raise PolicyError(f"policy 'policy:' key must be a mapping: {policy_path}")

    name = meta.get("name")
    version = meta.get("version")
    if not isinstance(name, str) or not isinstance(version, str):
        raise PolicyError(f"policy file must define string 'name' and 'version': {policy_path}")

    return PolicyBundle(path=str(policy_path), name=name, version=version, data=raw)


@lru_cache(maxsize=8)
def get_policy(path: str) -> PolicyBundle:
    return load_policy(path)
