#!/usr/bin/env bash
set -Eeuo pipefail
mkdir -p /tmp/doremi-probe
cp /mnt/Doremi.AppImage /tmp/doremi-probe/Doremi.AppImage
chmod +x /tmp/doremi-probe/Doremi.AppImage
sha256sum /mnt/Doremi.AppImage /tmp/doremi-probe/Doremi.AppImage
# Real negative probe runs in Docker, exercises an internal pipeline and must
# propagate exactly 42 through Docker and the host's tee (not just any failure).
if [[ "${DOREMI_PROBE_FORCE_FAILURE:-0}" == 1 ]]; then
  bash -c 'echo FORCED_SMOKE_FAILURE >&2; exit 42' | tee /probe-output/smoke.log
fi
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq libgl1 libegl1 libxkbcommon0 libdbus-1-3 libfontconfig1 libsm6 libxext6 libxrender1 libpulse0 python3 >/dev/null
ldconfig -p > /tmp/doremi-probe/system-libraries.txt
if grep -E 'libvlc(core)?\.so' /tmp/doremi-probe/system-libraries.txt; then
  echo 'SYSTEM_VLC_PRESENT: probe invalid' >&2
  exit 1
fi
echo SYSTEM_VLC_ABSENT
export QT_QPA_PLATFORM=offscreen
export XDG_CONFIG_HOME=/tmp/doremi-probe/config XDG_DATA_HOME=/tmp/doremi-probe/data XDG_CACHE_HOME=/tmp/doremi-probe/cache
export DOREMI_SMOKE_OUT=/probe-output/smoke.json
cd /tmp/doremi-probe
./Doremi.AppImage --appimage-extract-and-run --smoke-test 2>&1 | tee /probe-output/smoke.log
python3 /probe/validate-smoke.py "$DOREMI_SMOKE_OUT"
grep -Fq DOREMI_SMOKE_OK /probe-output/smoke.log
cat "$DOREMI_SMOKE_OUT"
