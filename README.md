# prebuilt-tools

Prebuilt ARM64 and AMD64 binaries for RTK, MinIO, and other development tools,
with versioned releases and checksums to speed up project setup and Docker builds.

This is the separate public `hplustree/prebuilt-tools` repository. Existing
production RTK downloads continue using `hplustree/rtk-debian-builds`; nothing
here renames, replaces, or modifies that repository or its releases.

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

Only a dispatch with `publish: true`, after both architecture jobs succeed,
can publish. The publisher requires the entire asset matrix and valid checksums,
requires a public repository, and refuses any target except
`hplustree/prebuilt-tools`. It creates a draft, uploads assets, then publishes.
An existing release is never overwritten; failed uploads remain a draft. Inspect
and remove an incomplete draft manually before retrying, or choose a new bundle
revision. Never modify the assets of an already published bundle.

Review the source/package notices and metadata before the first publication.
Keep corresponding source assets available alongside their binaries.

## Future RTK migration

Keep production on `hplustree/rtk-debian-builds` for now. RTK can later use its own
release namespace here. Copy old assets without rebuilding, compare checksums,
test the new URL, then explicitly change consumers. Existing RTK releases must
remain accessible for current deployments and rollbacks. This MinIO workflow
does not build, upload, or edit RTK releases.

## Offline tests

Install `requirements-dev.txt`, then run `python -m pytest tests -q`.
Tests mock Git, Go, and GitHub publication commands. They do not compile binaries,
run Docker builds, download upstream source, or publish releases.
