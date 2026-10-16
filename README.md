# prebuilt-tools

Prebuilt ARM64 and AMD64 binaries for RTK, MinIO, and other development tools,
with versioned releases and checksums to speed up project setup and Docker builds.

This is the separate public `hplustree/prebuilt-tools` repository. Existing
production RTK downloads continue using `hplustree/rtk-debian-builds`; nothing
here renames, replaces, or modifies that repository or its releases.

## Release availability

| Tool | ARM64 / AMD64 | Status |
|------|---------------|--------|
| RTK v0.29.0 | Linux Debian Bookworm | [Published](https://github.com/hplustree/prebuilt-tools/releases/tag/v0.29.0) |
| MinIO server + client | Linux, Alpine-compatible | [Build and review passed](https://github.com/hplustree/prebuilt-tools/actions/runs/38866210064); publication awaiting approval |

MinIO Docker downloads become available only after its release is published.

The first MinIO bundle (`minio-2025-09-07-mc-2025-08-13-r1`) was built from
`4d164e6` on 2026-10-16. Both native jobs passed checksum, Alpine executable,
and server/client upload-download checks. Artifact review verified all 24 files,
the four executable architecture headers, licenses, vendored sources, and pinned
build metadata. The publish job is waiting at the required-reviewer environment;
no MinIO draft or release has been created.

## MinIO releases

`minio/releases.env` pins a namespaced bundle tag, exact upstream release tags,
and their dereferenced Git commit IDs. Native Linux ARM64 and AMD64 runners build
the same source revisions with Go 1.24.2 and CGO disabled. An upstream tag that
moves fails the commit check. Both the server and client are packaged with their
AGPLv3 license and source/build metadata. Source archives contain the checked-out
source and vendored dependencies (including their license files), excluding `.git`.

Each architecture produces binary archives, corresponding source archives,
readable source/build metadata, and SHA-256 sidecars for every asset. Example:

```text
minio-RELEASE.2025-09-07T16-13-09Z-linux-arm64.tar.gz
minio-RELEASE.2025-09-07T16-13-09Z-linux-arm64.tar.gz.sha256
minio-RELEASE.2025-09-07T16-13-09Z-source-linux-arm64.tar.gz
minio-RELEASE.2025-09-07T16-13-09Z-source-linux-arm64.tar.gz.sha256
minio-RELEASE.2025-09-07T16-13-09Z-linux-arm64-SOURCE.txt
minio-RELEASE.2025-09-07T16-13-09Z-linux-arm64-SOURCE.txt.sha256
```

Equivalent files are produced for AMD64 and for `mc` at its pinned version.

## Manual preparation and publication

The workflow has **only `workflow_dispatch`**. Pushing code does not run builds.
Dispatching with the default `publish: false` runs builds and tests, then stores
artifacts in Actions; it creates no GitHub release. The workflow runs native
version checks, Alpine executable checks, and a server/client bucket upload and
download round trip before uploading artifacts.

Before dispatching with `publish: true`, configure the GitHub environment
`minio-release` with a **required reviewer** in Settings → Environments.
The workflow's publish job uses this environment. An environment name alone
provides no protection: keep the required-reviewer rule enabled.

To prepare a release:

1. Open Actions → Prepare MinIO binary release → Run workflow on `main`.
2. Select `publish: true` to build both architectures and wait at the review gate.
3. Review both build jobs, version/Alpine checks, the server/client round trip,
   artifact checksums, and source/build metadata.
4. Approve the `minio-release` environment only after that review. Approval
   starts the publish job; until then no draft or published release is created.
5. Verify the published release contains the complete ARM64/AMD64 asset matrix.

Only a dispatch with `publish: true`, after both architecture jobs succeed and
an environment reviewer approves, can publish. The publisher requires the
entire asset matrix and valid checksums,
requires a public repository, and refuses any target except
`hplustree/prebuilt-tools`. It creates a draft, uploads assets, then publishes.
An existing release is never overwritten; failed uploads remain a draft. Inspect
and remove an incomplete draft manually before retrying, or choose a new bundle
revision. Never modify the assets of an already published bundle.

Review the source/package notices and metadata before the first publication.
Keep corresponding source assets available alongside their binaries.

## RTK releases

[RTK v0.29.0](https://github.com/hplustree/prebuilt-tools/releases/tag/v0.29.0)
contains exact copies of the existing Debian Bookworm binaries for ARM64
(`aarch64`) and AMD64 (`x86_64`). The original archive filenames and bytes are
preserved; RTK was not rebuilt or repackaged. Each archive has a `.sha256`
sidecar, and `SHA256SUMS` lists both hashes. `PROVENANCE.json` records the
original release URL, asset IDs, sizes, and SHA-256 values. The same metadata
is recorded in `rtk/v0.29.0.json` and `rtk/v0.29.0-SHA256SUMS` in this repository.

The hashes were checked against GitHub's original asset digests and verified
again using anonymous downloads from the new release.

The [original RTK release](https://github.com/hplustree/rtk-debian-builds/releases/tag/v0.29.0)
remains unchanged and accessible. Production consumers still use that original
repository. Moving a consumer to `prebuilt-tools` is a separate launch change;
retain the old releases for existing deployments and rollbacks. The MinIO
workflow does not build, upload, or edit RTK releases.

## Offline tests

Install `requirements-dev.txt`, then run `python -m pytest tests -q`.
Tests mock Git, Go, and GitHub publication commands. They do not compile binaries,
run Docker builds, download upstream source, or publish releases.
