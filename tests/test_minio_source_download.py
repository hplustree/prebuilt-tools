"""Exercise source-download retries without network access or Docker builds."""

import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("succeed_on,expected_status,attempts", [(1, 0, 1), (3, 0, 3), (4, 128, 3)])
def test_clone_retries_clean_partial_downloads_and_preserve_http_version_and_release(
    tmp_path, succeed_on, expected_status, attempts
):
    """Mock Git, cleanup, and sleep so no real /src path is accessed."""
    commands = {
        "git": '''#!/bin/sh
set -eu
count=0
if [ -f "$TEST_DIR/count" ]; then count=$(cat "$TEST_DIR/count"); fi
count=$((count + 1))
echo "$count" > "$TEST_DIR/count"
printf '%s\\n' "$@" > "$TEST_DIR/args-$count"
if [ -f "$TEST_DIR/partial" ]; then exit 99; fi
if [ "$count" -lt "$SUCCEED_ON" ]; then
    touch "$TEST_DIR/partial"
    exit 128
fi
''',
        "rm": '''#!/bin/sh
set -eu
test "$#" = 2 && test "$1" = -rf && test "$2" = "$TEST_DIR/checkout"
echo cleanup >> "$TEST_DIR/cleanups"
/bin/rm -f "$TEST_DIR/partial"
''',
        "sleep": '''#!/bin/sh
echo "$1" >> "$TEST_DIR/delays"
''',
    }
    for name, source in commands.items():
        path = tmp_path / name
        path.write_text(source)
        path.chmod(0o755)
    result = subprocess.run(
        ["sh", str(ROOT / "minio/clone-source.sh"), "https://github.com/minio/minio.git", "pinned-release", str(tmp_path / "checkout")],
        env={**os.environ, "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
             "TEST_DIR": str(tmp_path), "SUCCEED_ON": str(succeed_on)},
        capture_output=True, text=True,
    )
    assert result.returncode == expected_status, result.stderr
    assert int((tmp_path / "count").read_text()) == attempts
    for attempt in range(1, attempts + 1):
        assert (tmp_path / f"args-{attempt}").read_text().splitlines() == [
            "-c", "http.version=HTTP/1.1", "clone", "--depth", "1", "--single-branch",
            "--branch", "pinned-release", "https://github.com/minio/minio.git", str(tmp_path / "checkout"),
        ]
    delays = tmp_path / "delays"
    assert (delays.read_text().splitlines() if delays.exists() else []) == ["5", "10"][: attempts - 1]
    cleanups = tmp_path / "cleanups"
    failures = attempts if expected_status else attempts - 1
    assert (cleanups.read_text().splitlines() if cleanups.exists() else []) == ["cleanup"] * failures
    assert not (tmp_path / "partial").exists()
    if expected_status:
        assert "failed after 3 attempts" in result.stderr


def test_release_builder_uses_retry_helper_and_verifies_pinned_source_commits():
    builder = (ROOT / "minio/build-release.sh").read_text()
    assert 'sh "$script_dir/clone-source.sh" "$repository" "$version" "$source_dir"' in builder
    assert 'test "$commit" = "$expected_commit"' in builder
    assert "MINIO_COMMIT=" in (ROOT / "minio/releases.env").read_text()
    assert "MC_COMMIT=" in (ROOT / "minio/releases.env").read_text()
