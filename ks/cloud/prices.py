"""Spot prices from the Cloud Billing Catalog API (GCP.md §6) -> costs/prices.yaml.

A machine's hourly price is assembled from its parts: the spot GPU SKU, the
family's spot vCPU and RAM SKUs times the machine shape, and any local SSD
the machine type bundles. ``assemble()`` is pure and unit-tested against a
saved slice of the real API response; ``fetch()`` does the HTTP.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
import yaml

from ks.cloud.config import HOURS_PER_MONTH, PRICES_PATH

COMPUTE_SERVICE = "6F81-5844-456A"  # verified via /v1/services on 2026-10-21
VERTEX_SERVICE = "C7E2-9256-1C43"
CATALOG = "https://cloudbilling.googleapis.com/v1"

MACHINES = ["g2-standard-8", "a2-ultragpu-1g", "a3-highgpu-1g", "e2-standard-2"]
REGIONS = ["us-central1", "europe-west4"]
LOCAL_SSD_PARTITION_GIB = 375

# accelerator type -> how the Catalog names its spot SKU
GPU_SKU_NAME = {
    "nvidia-l4": "Nvidia L4",
    "nvidia-a100-80gb": "Nvidia Tesla A100 80GB",
    "nvidia-h100-80gb": "Nvidia H100 80GB",
}


class PriceError(RuntimeError):
    pass


@dataclass(frozen=True)
class Shape:
    machine: str
    vcpus: int
    memory_gib: float
    gpu: str | None
    gpus: int
    local_ssd_gib: int

    @property
    def family(self) -> str:
        return self.machine.split("-", 1)[0].upper()  # g2-standard-8 -> G2


def unit_price(sku: dict[str, Any]) -> tuple[float, str]:
    """(USD per unit, unit). Takes the highest tier so a free tier never hides a cost."""
    expr = sku["pricingInfo"][0]["pricingExpression"]
    rates = [
        int(t["unitPrice"].get("units", 0)) + t["unitPrice"].get("nanos", 0) / 1e9
        for t in expr["tieredRates"]
    ]
    return max(rates), expr["usageUnit"]


def _one(skus: list[dict], region: str, pattern: str, usage_type: str, unit: str) -> dict:
    rx = re.compile(pattern)
    hits = [
        s
        for s in skus
        if rx.match(s["description"])
        and s["category"].get("usageType") == usage_type
        and region in s.get("serviceRegions", [])
    ]
    if len(hits) != 1:
        found = [s["description"] for s in hits]
        raise PriceError(f"{region}: expected exactly one SKU for /{pattern}/, found {found}")
    _, got = unit_price(hits[0])
    if got != unit:
        raise PriceError(f"{hits[0]['description']}: unit {got}, expected {unit}")
    return hits[0]


def assemble(skus: list[dict], shapes: list[Shape], regions: list[str]) -> dict[str, Any]:
    """Region -> machine -> whole-VM spot price, plus the disk price."""
    out: dict[str, Any] = {"gce_spot": {}, "disk": {}}
    disk_prices = []
    for region in regions:
        table: dict[str, Any] = {}
        for sh in shapes:
            fam = sh.family
            core = _one(
                skus,
                region,
                rf"^Spot Preemptible {fam} Instance Core running in ",
                "Preemptible",
                "h",
            )
            ram = _one(
                skus,
                region,
                rf"^Spot Preemptible {fam} Instance Ram running in ",
                "Preemptible",
                "GiBy.h",
            )
            parts = {"core": core, "ram": ram}
            total = sh.vcpus * unit_price(core)[0] + sh.memory_gib * unit_price(ram)[0]
            if sh.gpu:
                name = re.escape(GPU_SKU_NAME[sh.gpu])
                gpu = _one(
                    skus,
                    region,
                    rf"^{name} GPU attached to Spot Preemptible VMs running in ",
                    "Preemptible",
                    "h",
                )
                parts["gpu"] = gpu
                total += sh.gpus * unit_price(gpu)[0]
            if sh.local_ssd_gib:
                ssd = _one(
                    skus,
                    region,
                    r"^SSD backed Local Storage attached to Spot Preemptible VMs",
                    "Preemptible",
                    "GiBy.mo",
                )
                parts["local_ssd"] = ssd
                total += sh.local_ssd_gib * unit_price(ssd)[0] / HOURS_PER_MONTH
            table[sh.machine] = {
                "gpu": sh.gpu or "none",
                "gpus": sh.gpus,
                "vcpus": sh.vcpus,
                "memory_gib": sh.memory_gib,
                "local_ssd_gib": sh.local_ssd_gib,
                "usd_per_hour": round(total, 6),
                "skus": {k: f"{v['skuId']} {v['description']}" for k, v in parts.items()},
            }
        out["gce_spot"][region] = table
        disk = _one(skus, region, r"^Balanced PD Capacity( in .*)?$", "OnDemand", "GiBy.mo")
        disk_prices.append(unit_price(disk)[0])
    out["disk"]["pd-balanced_usd_per_gb_month"] = max(disk_prices)
    return out


# --- I/O ---------------------------------------------------------------------


def _gcloud(*args: str) -> str:
    gcloud = str(Path("~/google-cloud-sdk/bin/gcloud").expanduser())
    return subprocess.run([gcloud, *args], check=True, capture_output=True, text=True).stdout


def shape_of(machine: str, zone: str, project: str) -> Shape:
    d = yaml.safe_load(
        _gcloud(
            "compute",
            "machine-types",
            "describe",
            machine,
            f"--zone={zone}",
            f"--project={project}",
            "--format=json",
        )
    )
    accels = d.get("accelerators") or []
    ssd = d.get("bundledLocalSsds") or {}
    return Shape(
        machine=machine,
        vcpus=int(d["guestCpus"]),
        memory_gib=int(d["memoryMb"]) / 1024,
        gpu=accels[0]["guestAcceleratorType"] if accels else None,
        gpus=int(accels[0]["guestAcceleratorCount"]) if accels else 0,
        local_ssd_gib=int(ssd.get("partitionCount", 0)) * LOCAL_SSD_PARTITION_GIB,
    )


def fetch_skus(service: str, project: str) -> list[dict]:
    token = _gcloud("auth", "print-access-token").strip()
    headers = {"Authorization": f"Bearer {token}", "X-Goog-User-Project": project}
    skus: list[dict] = []
    page = ""
    while True:
        params = {"currencyCode": "USD", "pageSize": "5000"} | ({"pageToken": page} if page else {})
        r = requests.get(
            f"{CATALOG}/services/{service}/skus", headers=headers, params=params, timeout=60
        )
        r.raise_for_status()
        d = r.json()
        skus += d.get("skus", [])
        page = d.get("nextPageToken", "")
        if not page:
            return skus


def fetch(project: str, now: datetime, path: Path = PRICES_PATH) -> dict[str, Any]:
    """Fetch, assemble and write prices.yaml with verified: false."""
    shapes = [shape_of(m, "us-central1-a", project) for m in MACHINES]
    table = assemble(fetch_skus(COMPUTE_SERVICE, project), shapes, REGIONS)
    doc = {
        "verified": False,
        "fetched_on": now.replace(microsecond=0),
        "source": f"Cloud Billing Catalog API, service {COMPUTE_SERVICE}, list prices in USD",
        **table,
        "storage": {"gcs_standard_usd_per_gb_month": 0.02},
        "vertex_training_spot": {},  # the vertex credit does not cover custom training (ADR-013)
        "gemini": {},  # filled in when Gemini baselines run (after 2026-11-12)
    }
    header = (
        "# Hourly prices per whole machine (GPU + vCPU + RAM + bundled local SSD), spot, USD.\n"
        "# Written by `ks prices`. The boot disk is added per run from `disk`.\n"
        "# ks launch refuses to run while verified is false or the file is > 30 days old.\n"
    )
    path.write_text(header + yaml.safe_dump(doc, sort_keys=False, width=120))
    return doc
