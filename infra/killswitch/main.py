"""Cloud Run function `ks-killswitch`: Pub/Sub topic ks-budget -> decide -> act.

Configuration (env vars, set by deploy.sh):
  KS_PROJECT         the project to protect
  KS_REGIONS         comma-separated Vertex regions to cancel jobs in
  KS_DETACH_BILLING  "1" only if the user opted in (dedicated project)
"""

from __future__ import annotations

import json
import os

import functions_framework
import google.auth
from google.auth.transport.requests import AuthorizedSession
from killswitch_decision import act, decide, parse


@functions_framework.cloud_event
def handle(cloud_event) -> None:
    project = os.environ["KS_PROJECT"]
    regions = [r for r in os.environ.get("KS_REGIONS", "us-central1").split(",") if r]
    detach_enabled = os.environ.get("KS_DETACH_BILLING") == "1"

    n = parse(cloud_event.data["message"])
    d = decide(n, detach_enabled=detach_enabled)
    actions: list[str] = []
    if d.stop:
        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        actions = act(d, AuthorizedSession(creds), project, regions)
    print(
        json.dumps(
            {
                "severity": "ALERT" if d.stop else "INFO",
                "message": f"ks-killswitch: {d.reason}",
                "budget": n.budget,
                "cost": n.cost,
                "amount": n.amount,
                "stop": d.stop,
                "detach": d.detach,
                "actions": actions,
            }
        )
    )
