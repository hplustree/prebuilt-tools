#!/bin/sh
# Retry interrupted clones from a clean destination, preserving the pinned ref.
set -eu

repository="$1"
release="$2"
destination="${3:?Pass a temporary checkout destination}"
case "$destination" in /|.|..|'') echo "Unsafe checkout destination" >&2; exit 1 ;; esac
attempt=1
while :; do
    if git -c http.version=HTTP/1.1 clone --depth 1 --single-branch \
        --branch "$release" "$repository" "$destination"; then
        exit 0
    else
        status=$?
    fi

    # A failed clone can leave files that prevent the next clone from starting.
    rm -rf "$destination"
    if [ "$attempt" -ge 3 ]; then
        echo "Source download failed after $attempt attempts: $repository ($release)" >&2
        exit "$status"
    fi
    delay=$((attempt * 5))
    echo "Source download failed; retrying in ${delay}s (attempt $((attempt + 1))/3)" >&2
    sleep "$delay"
    attempt=$((attempt + 1))
done
