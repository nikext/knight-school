"""SKU -> machine price assembly, against a saved slice of the real Catalog API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ks.cloud.prices import PriceError, Shape, assemble, unit_price

SKUS = json.loads((Path(__file__).parent / "fixtures" / "catalog_compute_skus.json").read_text())

# shapes as `gcloud compute machine-types describe` reported them on 2026-10-21
SHAPES = [
    Shape("g2-standard-8", 8, 32, "nvidia-l4", 1, 0),
    Shape("a2-ultragpu-1g", 12, 170, "nvidia-a100-80gb", 1, 375),
    Shape("a3-highgpu-1g", 26, 234, "nvidia-h100-80gb", 1, 750),
    Shape("e2-standard-2", 2, 8, None, 0, 0),
]


@pytest.fixture(scope="module")
def table():
    return assemble(SKUS, SHAPES, ["us-central1", "europe-west4"])


def test_l4_machine_is_gpu_plus_vcpus_plus_ram(table):
    # 0.3352 GPU + 8 x 0.01495 vCPU + 32 x 0.001751 GiB
    assert table["gce_spot"]["us-central1"]["g2-standard-8"]["usd_per_hour"] == pytest.approx(
        0.510832
    )


def test_a100_includes_its_bundled_local_ssd(table):
    # 2.3568 + 12 x 0.01897 + 170 x 0.002542 + 375 GiB x 0.0455 / 730
    m = table["gce_spot"]["us-central1"]["a2-ultragpu-1g"]
    assert m["usd_per_hour"] == pytest.approx(3.039953, abs=1e-6)
    assert "local_ssd" in m["skus"]


def test_h100_ignores_mega_and_plus_skus(table):
    m = table["gce_spot"]["us-central1"]["a3-highgpu-1g"]
    assert m["usd_per_hour"] == pytest.approx(6.273933, abs=1e-6)
    assert "Mega" not in m["skus"]["gpu"] and "Plus" not in m["skus"]["gpu"]


def test_cpu_only_machine_has_no_gpu_part(table):
    m = table["gce_spot"]["us-central1"]["e2-standard-2"]
    assert m["gpus"] == 0 and "gpu" not in m["skus"] and 0 < m["usd_per_hour"] < 0.1


def test_regions_are_priced_separately(table):
    us = table["gce_spot"]["us-central1"]["g2-standard-8"]["usd_per_hour"]
    eu = table["gce_spot"]["europe-west4"]["g2-standard-8"]["usd_per_hour"]
    assert us != eu
    assert "Netherlands" in table["gce_spot"]["europe-west4"]["g2-standard-8"]["skus"]["gpu"]


def test_disk_price_is_the_max_over_regions(table):
    assert table["disk"]["pd-balanced_usd_per_gb_month"] >= 0.1


def test_missing_sku_fails_loudly():
    no_l4 = [s for s in SKUS if not s["description"].startswith("Nvidia L4 GPU attached to Spot")]
    with pytest.raises(PriceError, match="expected exactly one SKU"):
        assemble(no_l4, SHAPES[:1], ["us-central1"])


def test_ambiguous_sku_fails_loudly():
    dup = SKUS + [s for s in SKUS if s["description"].startswith("Nvidia L4 GPU attached to Spot")]
    with pytest.raises(PriceError, match="found"):
        assemble(dup, SHAPES[:1], ["us-central1"])


def test_unit_price_takes_the_highest_tier():
    sku = {
        "pricingInfo": [
            {
                "pricingExpression": {
                    "usageUnit": "h",
                    "tieredRates": [
                        {"startUsageAmount": 0, "unitPrice": {"units": "0", "nanos": 0}},
                        {"startUsageAmount": 10, "unitPrice": {"units": "1", "nanos": 500000000}},
                    ],
                }
            }
        ]
    }
    assert unit_price(sku) == (1.5, "h")
