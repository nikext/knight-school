#!/bin/bash
# Shutdown script for every ks VM. GCE gives a spot VM ~30 s on preemption;
# use them to leave a marker so the watcher knows why the VM vanished.
# After a normal end the `ended` marker exists and this does nothing.
MD=http://metadata.google.internal/computeMetadata/v1/instance
md() { curl -sf -H 'Metadata-Flavor: Google' "$MD/$1"; }

PREFIX="$(md attributes/ks-bucket)/runs/$(md attributes/ks-run-id)/attempts/$(md attributes/ks-attempt)"
gcloud storage ls "$PREFIX/ended" >/dev/null 2>&1 && exit 0

if [[ "$(md preempted)" == "TRUE" ]]; then marker=preempted; else marker=shutdown; fi
printf '{"ts":"%s"}\n' "$(date -u +%FT%TZ)" | gcloud storage cp - "$PREFIX/$marker" --quiet
