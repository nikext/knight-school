"""Typed views of costs/caps.yaml, costs/prices.yaml, run configs and .env.

Everything money-related is validated here before the gate sees it, so a typo
in a YAML file becomes a clear error instead of a silently wrong number.
"""

from __future__ import annotations

import os
import re
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

REPO = Path(__file__).resolve().parents[2]
CAPS_PATH = REPO / "costs" / "caps.yaml"
PRICES_PATH = REPO / "costs" / "prices.yaml"
LEDGER_PATH = REPO / "costs" / "ledger.jsonl"
ENV_PATH = REPO / ".env"

HOURS_PER_MONTH = 730  # GCP's conversion for GiBy.mo prices

# Deep Learning VM family with the NVIDIA driver, Docker and the container
# toolkit (checked with `gcloud compute images list` on 2026-10-21).
DEFAULT_VM_IMAGE_FAMILY = "common-cu129-ubuntu-2404-nvidia-580"
DEFAULT_VM_IMAGE_PROJECT = "deeplearning-platform-release"


class CapsError(ValueError):
    """caps.yaml is malformed or inconsistent; nothing may launch."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- caps.yaml --------------------------------------------------------------


class Pool(_Strict):
    credit: str
    scope: str
    remaining_usd: float | None = None
    checked_on: datetime | None = None
    expires: date | None = None
    usable_from: date | None = None
    covers_custom_training: bool = False
    ceiling: float = Field(ge=0)

    def expires_at(self) -> datetime | None:
        # Midnight UTC is earlier than midnight Pacific (billing's clock), so
        # treating the date as 00:00Z errs on the safe side.
        return datetime.combine(self.expires, time(0), UTC) if self.expires else None

    def usable_from_at(self) -> datetime | None:
        return datetime.combine(self.usable_from, time(0), UTC) if self.usable_from else None


class Limits(_Strict):
    max_hours_per_job: float = 24
    max_gpus_per_job: int = 1
    spot_only: bool = True
    worst_case_factor: float = 1.05
    prices_max_age_days: int = 30
    credit_reserve_factor: float = 0.9
    credit_check_max_age_days: int = 7
    expiry_margin_hours: float = 48


class Caps(_Strict):
    currency: Literal["USD"]
    pools: dict[str, Pool]
    allocations: dict[str, dict[str, float]]
    limits: Limits

    def problems(self) -> list[str]:
        """Consistency rules for caps.yaml. Any problem blocks every launch."""
        out: list[str] = []
        if set(self.allocations) != set(self.pools):
            out.append(
                f"allocations pools {sorted(self.allocations)} != pools {sorted(self.pools)}"
            )
        for name, alloc in self.allocations.items():
            pool = self.pools.get(name)
            if pool is None:
                continue
            if "contingency" not in alloc:
                out.append(f"pool {name}: allocations have no 'contingency' line")
            negative = [m for m, v in alloc.items() if v < 0]
            if negative:
                out.append(f"pool {name}: negative allocations {negative}")
            total = sum(alloc.values())
            if abs(total - pool.ceiling) > 0.005:
                out.append(
                    f"pool {name}: allocations sum to {total:.2f}, ceiling is {pool.ceiling:.2f}"
                )
        return out


def load_caps(path: Path = CAPS_PATH) -> Caps:
    try:
        caps = Caps.model_validate(yaml.safe_load(path.read_text()))
    except Exception as e:  # pydantic or yaml error
        raise CapsError(f"{path}: {e}") from e
    if problems := caps.problems():
        raise CapsError(f"{path}: " + "; ".join(problems))
    return caps


# --- prices.yaml ------------------------------------------------------------


class MachinePrice(_Strict):
    gpu: str
    gpus: int
    vcpus: int | None = None
    memory_gib: float | None = None
    local_ssd_gib: int = 0
    usd_per_hour: float = Field(gt=0)
    skus: dict[str, str] = {}


class Prices(_Strict):
    verified: bool
    fetched_on: datetime | None = None
    source: str
    gce_spot: dict[str, dict[str, MachinePrice]]  # region -> machine -> price
    disk: dict[str, float]
    storage: dict[str, float] = {}
    vertex_training_spot: dict = {}
    gemini: dict = {}

    def machine(self, region: str, machine: str) -> MachinePrice | None:
        return self.gce_spot.get(region, {}).get(machine)

    def disk_usd_per_hour(self, gb: int) -> float:
        return gb * self.disk["pd-balanced_usd_per_gb_month"] / HOURS_PER_MONTH


def load_prices(path: Path = PRICES_PATH) -> Prices:
    return Prices.model_validate(yaml.safe_load(path.read_text()))


# --- run configs (configs/runs/*.yaml) --------------------------------------

_ID = re.compile(r"^m[0-9]-[a-z0-9]+(-[a-z0-9]+)*$")


class RunConfig(_Strict):
    id: str
    milestone: str
    description: str = ""
    pool: Literal["compute", "vertex"] = "compute"
    backend: Literal["gce", "vertex"] = "gce"
    machine: str
    gpus: int = 1
    spot: bool = True
    zones: list[str] = Field(min_length=1)
    max_hours: float
    max_attempts: int = Field(default=3, ge=1, le=10)
    run_budget_usd: float | None = None  # approved total over all attempts
    boot_disk_gb: int = Field(default=200, ge=10, le=2000)
    image: str
    command: str
    env: dict[str, str] = {}
    vm_image_family: str = DEFAULT_VM_IMAGE_FAMILY
    vm_image_project: str = DEFAULT_VM_IMAGE_PROJECT

    @field_validator("id")
    @classmethod
    def _id_ok(cls, v: str) -> str:
        # Instance names are ks-<id>-a<n> and must fit GCE's 63 characters.
        if not _ID.match(v) or len(v) > 50:
            raise ValueError(f"run id {v!r} must look like m3-e2-dense-r1 (<= 50 chars)")
        return v

    @field_validator("zones")
    @classmethod
    def _zones_ok(cls, v: list[str]) -> list[str]:
        for z in v:
            if not re.match(r"^[a-z]+-[a-z]+[0-9]+-[a-z]$", z):
                raise ValueError(f"zone {z!r} is not a GCE zone name")
        return v

    def regions(self) -> list[str]:
        return list(dict.fromkeys(zone_region(z) for z in self.zones))

    def instance_name(self, attempt: int) -> str:
        return f"ks-{self.id}-a{attempt}"


def zone_region(zone: str) -> str:
    return zone.rsplit("-", 1)[0]


def load_run(path: Path) -> RunConfig:
    return RunConfig.model_validate(yaml.safe_load(Path(path).read_text()))


# --- .env -------------------------------------------------------------------


def read_env(path: Path = ENV_PATH) -> dict[str, str]:
    """KEY=VALUE lines from .env, overridden by the process environment."""
    env: dict[str, str] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    env.update({k: v for k, v in os.environ.items() if k in env or k.startswith("KS_")})
    return env


def utcnow() -> datetime:
    return datetime.now(UTC)
