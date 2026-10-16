#!/bin/bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
source "$script_dir/releases.env"
output="$(cd -- "${1:?Pass artifact directory}" && pwd)"
architecture="${2:?Pass architecture}"
work="$(mktemp -d)"
pid=''
trap 'if [ -n "$pid" ]; then kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi; rm -rf "$work"' EXIT
tar -xzf "$output/minio-$MINIO_VERSION-linux-$architecture.tar.gz" -C "$work" minio
tar -xzf "$output/mc-$MC_VERSION-linux-$architecture.tar.gz" -C "$work" mc
export MINIO_ROOT_USER=release-test-user MINIO_ROOT_PASSWORD=release-test-password
"$work/minio" server "$work/data" --address 127.0.0.1:19000 --console-address 127.0.0.1:19001 > "$work/server.log" 2>&1 &
pid=$!
curl -fsS --retry 30 --retry-connrefused --retry-delay 1 --retry-max-time 60 \
    http://127.0.0.1:19000/minio/health/live || { cat "$work/server.log" >&2; exit 1; }
"$work/mc" --config-dir "$work/config" alias set test http://127.0.0.1:19000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
"$work/mc" --config-dir "$work/config" mb test/release-check
printf 'minio release round trip\n' > "$work/input"
"$work/mc" --config-dir "$work/config" cp "$work/input" test/release-check/object
"$work/mc" --config-dir "$work/config" cat test/release-check/object > "$work/output"
cmp "$work/input" "$work/output"
