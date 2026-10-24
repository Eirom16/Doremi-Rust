#!/usr/bin/env bash
# Host boundary: preserve Docker, tee and report-validation exit codes.
set -Eeuo pipefail
image=$(readlink -f "$1")
distro=$2
output=$3
case "$distro" in 22.04|24.04) ;; *) echo 'Unsupported probe distro' >&2; exit 2 ;; esac
marker="CLEAN_ENV_${distro//./}"
trap 'rc=$?; printf "%s=FAIL exit=%s\n" "$marker" "$rc" >&2; exit "$rc"' ERR
test -f "$image"
mkdir -p "$output"
output=$(cd "$output" && pwd)
probe_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# A successful Docker no-op must not reuse a report from an earlier run.
rm -f "$output/smoke.json" "$output/smoke.log"
docker run --rm \
  -v "$image:/mnt/Doremi.AppImage:ro" \
  -v "$probe_dir:/probe:ro" \
  -v "$output:/probe-output" \
  -e "DOREMI_PROBE_FORCE_FAILURE=${DOREMI_PROBE_FORCE_FAILURE:-0}" \
  "ubuntu:$distro" bash /probe/probe-container.sh 2>&1 | tee "$output/docker.log"
python3 "$probe_dir/validate-smoke.py" "$output/smoke.json"
grep -Fq 'DOREMI_SMOKE_OK' "$output/smoke.log"
printf '%s=PASS (ubuntu:%s; no system VLC; validated JSON)\n' "$marker" "$distro"
