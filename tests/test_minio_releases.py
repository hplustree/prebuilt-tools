"""Verify release consumers and publication guards without builds or network calls."""

import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PREBUILT = ROOT
PINS = dict(
    line.split("=", 1) for line in (ROOT / "minio/releases.env").read_text().splitlines()
    if line and not line.startswith("#")
)


def _executable(path, source):
    path.write_text(source)
    path.chmod(0o755)



@pytest.fixture
def release_environment(tmp_path):
    """Use real archives/hashes, with downloads and GitHub commands mocked."""
    commands = tmp_path / "bin"
    commands.mkdir()
    assets = tmp_path / "assets"
    assets.mkdir()
    requests = tmp_path / "requests"
    _executable(commands / "curl", f'''#!{sys.executable}
import os, pathlib, shutil, sys
args = sys.argv[1:]
with open(os.environ['REQUEST_LOG'], 'a') as log:
    log.write(__import__('json').dumps(args) + '\\n')
if os.environ.get('FAIL_DOWNLOAD') == '1': sys.exit(22)
source = pathlib.Path(os.environ['TEST_ASSETS']) / args[-1].rsplit('/', 1)[-1]
if not source.exists(): sys.exit(22)
shutil.copyfile(source, args[args.index('-o') + 1])
''')
    # macOS has shasum; Alpine/Linux has sha256sum. Both execute real verification.
    _executable(commands / "sha256sum", '#!/bin/sh\nexec shasum -a 256 "$@"\n')
    _executable(commands / "gh", f'''#!{sys.executable}
import json, os, sys
args = sys.argv[1:]
with open(os.environ['GH_LOG'], 'a') as log: log.write(json.dumps(args) + '\\n')
if args[:2] == ['repo', 'view']: print('false')
elif args[:2] == ['release', 'create'] and os.environ.get('FAIL_CREATE') == '1': sys.exit(1)
''')
    return {
        **os.environ, "PATH": str(commands) + os.pathsep + os.environ["PATH"],
        "TEST_ASSETS": str(assets), "REQUEST_LOG": str(requests),
        "GH_LOG": str(tmp_path / "gh.log"),
        "RELEASE_REPOSITORY": "hplustree/prebuilt-tools",
        "PREBUILT_TOOLS_REPOSITORY": "hplustree/prebuilt-tools",
        "COPYFILE_DISABLE": "1",
    }



def _checksum(path, filename=None):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    Path(str(path) + ".sha256").write_text(f"{digest}  {filename or path.name}\n")



def _archive(environment, component, architecture, binary=None):
    version = PINS["MINIO_VERSION" if component == "minio" else "MC_VERSION"]
    path = Path(environment["TEST_ASSETS"]) / f"{component}-{version}-linux-{architecture}.tar.gz"
    binary = binary if binary is not None else f'#!/bin/sh\necho "{component} version {version}"\n'.encode()
    with tarfile.open(path, "w:gz") as archive:
        for name, data in [(component, binary), ("LICENSE", b"test license"), ("SOURCE.txt", b"test source")]:
            member = tarfile.TarInfo(name)
            member.mode = 0o644
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    _checksum(path)
    return path



def _publisher_assets(environment):
    assets = Path(environment["TEST_ASSETS"])
    for component in ["minio", "mc"]:
        version = PINS["MINIO_VERSION" if component == "minio" else "MC_VERSION"]
        for architecture in ["arm64", "amd64"]:
            _archive(environment, component, architecture)
            for name in [f"{component}-{version}-source-linux-{architecture}.tar.gz", f"{component}-{version}-linux-{architecture}-SOURCE.txt"]:
                asset = assets / name
                asset.write_bytes(b"source fixture, not a built binary")
                _checksum(asset)
    return assets



@pytest.mark.parametrize("failure", [None, "wrong-repository", "missing-architecture", "bad-checksum", "create-failed"])
def test_publication_requires_complete_valid_assets_and_never_overwrites(release_environment, failure):
    assets = _publisher_assets(release_environment)
    if failure == "wrong-repository": release_environment["RELEASE_REPOSITORY"] = "hplustree/rtk-debian-builds"
    if failure == "missing-architecture": next(assets.glob("minio-*-linux-amd64.tar.gz")).unlink()
    if failure == "bad-checksum": next(assets.glob("mc-*-linux-arm64.tar.gz")).write_bytes(b"tampered")
    if failure == "create-failed": release_environment["FAIL_CREATE"] = "1"
    result = subprocess.run(["bash", str(PREBUILT / "minio/publish-release.sh"), str(assets)], env=release_environment, capture_output=True, text=True)
    log = Path(release_environment["GH_LOG"])
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    assert (result.returncode == 0) == (failure is None), result.stderr
    if failure in {"wrong-repository", "missing-architecture", "bad-checksum"}:
        assert not calls
    else:
        assert calls[0][:2] == ["repo", "view"]
        assert calls[1][:2] == ["release", "create"]
        assert "--draft" in calls[1]
        assert "--clobber" not in calls[1]
        assert PINS["MINIO_BUNDLE_RELEASE"] in calls[1]
        if failure == "create-failed": assert len(calls) == 2
        else: assert calls[2][:2] == ["release", "edit"] and "--draft=false" in calls[2]



def test_separate_workflow_is_manual_and_requires_both_architectures_before_publication():
    workflow = yaml.safe_load((PREBUILT / ".github/workflows/minio-release.yml").read_text())
    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert workflow["on"]["workflow_dispatch"]["inputs"]["publish"]["default"] is False
    matrix = workflow["jobs"]["build"]["strategy"]["matrix"]["include"]
    assert matrix == [{"arch": "arm64", "runner": "ubuntu-24.04-arm"}, {"arch": "amd64", "runner": "ubuntu-24.04"}]
    assert workflow["jobs"]["publish"]["if"] == "inputs.publish"
    assert workflow["jobs"]["publish"]["needs"] == "build"
    assert workflow["permissions"] == {"contents": "read"}
    steps = workflow["jobs"]["build"]["steps"]
    assert any("Alpine" in step.get("name", "") for step in steps)
    assert any("smoke-test.sh" in step.get("run", "") for step in steps)
    assert (ROOT / ".github/workflows/minio-release.yml").exists()



@pytest.mark.parametrize("architecture", ["arm64", "amd64"])
@pytest.mark.parametrize("moved_tag", [False, True])
def test_release_packaging_with_mocked_git_and_go(release_environment, tmp_path, architecture, moved_tag):
    """Exercise packaging only: fake Git and Go produce fixtures, never compiled binaries."""
    commands = tmp_path / "bin"
    _executable(commands / "uname", '#!/bin/sh\necho ' + ("aarch64" if architecture == "arm64" else "x86_64") + '\n')
    _executable(commands / "git", f'''#!{sys.executable}
import os, pathlib, sys
args = sys.argv[1:]
if args[:2] == ['rev-parse', 'HEAD']:
    key = 'MINIO_COMMIT' if pathlib.Path.cwd().name == 'minio-source' else 'MC_COMMIT'
    print('wrong-commit' if os.environ.get('MOVED_TAG') == '1' else os.environ[key])
elif 'clone' in args:
    path = pathlib.Path(args[-1]); path.mkdir()
    (path / 'LICENSE').write_text('source license fixture')
    (path / 'go.mod').write_text('module fixture')
    (path / '.git').mkdir()
    (path / '.git' / 'config').write_text('must not be archived')
else: sys.exit(1)
''')
    _executable(commands / "go", f'''#!{sys.executable}
import json, os, pathlib, sys
from datetime import datetime
args = sys.argv[1:]
component = 'minio' if pathlib.Path.cwd().name == 'minio-source' else 'mc'
version = os.environ['MINIO_VERSION' if component == 'minio' else 'MC_VERSION']
with open(os.environ['GO_LOG'], 'a') as log: log.write(json.dumps(args) + '\\n')
if args == ['mod', 'vendor']:
    path = pathlib.Path('vendor/dependency'); path.mkdir(parents=True)
    (path / 'LICENSE').write_text('dependency license fixture')
elif args[0] == 'run':
    assert args[-1] == datetime.strptime(version, 'RELEASE.%Y-%m-%dT%H-%M-%SZ').strftime('%Y-%m-%dT%H:%M:%SZ')
    assert os.environ[component.upper() + '_RELEASE'] == 'RELEASE'
    print('-s -w -X fixture.ReleaseTag=' + version)
elif args[0] == 'build':
    assert os.environ['CGO_ENABLED'] == '0' and os.environ['GOTOOLCHAIN'] == 'local'
    assert '-mod=vendor' in args
    path = pathlib.Path(args[args.index('-o') + 1])
    path.write_text('#!/bin/sh\\necho "' + component + ' version ' + version + '"\\n'); path.chmod(0o755)
elif args == ['version']: print('go version go1.24.2 linux/fixture')
else: sys.exit(1)
''')
    output = tmp_path / "packaged"
    env = {**release_environment, **PINS, "MOVED_TAG": str(int(moved_tag)), "GO_LOG": str(tmp_path / "go.log")}
    result = subprocess.run(["bash", str(PREBUILT / "minio/build-release.sh"), architecture, str(output)], env=env, text=True, capture_output=True)
    assert (result.returncode == 0) is (not moved_tag), result.stderr
    if moved_tag:
        assert not (tmp_path / "go.log").exists()
        assert not list(output.glob("*.tar.gz"))
        return
    for component in ["minio", "mc"]:
        version = PINS["MINIO_VERSION" if component == "minio" else "MC_VERSION"]
        archive = output / f"{component}-{version}-linux-{architecture}.tar.gz"
        assert archive.exists()
        with tarfile.open(archive) as package:
            assert set(package.getnames()) == {component, "LICENSE", "SOURCE.txt"}
            metadata = package.extractfile("SOURCE.txt").read().decode()
            assert PINS["MINIO_COMMIT" if component == "minio" else "MC_COMMIT"] in metadata
        source = output / f"{component}-{version}-source-linux-{architecture}.tar.gz"
        with tarfile.open(source) as package:
            names = package.getnames()
            assert './vendor/dependency/LICENSE' in names
            assert not any('/.git' in name for name in names)
        for asset in [archive, source, output / f"{component}-{version}-linux-{architecture}-SOURCE.txt"]:
            assert Path(str(asset) + '.sha256').read_text() == hashlib.sha256(asset.read_bytes()).hexdigest() + '  ' + asset.name + '\n'
