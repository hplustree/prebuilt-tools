#!/bin/bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
source "$script_dir/releases.env"
repository="${RELEASE_REPOSITORY:?Set the separate release repository}"
if [ "$repository" != hplustree/prebuilt-tools ]; then
    echo "Refusing to publish outside hplustree/prebuilt-tools" >&2
    exit 1
fi
output="$(cd -- "${1:?Pass artifact directory}" && pwd)"
cd "$output"
for architecture in arm64 amd64; do
    for component in minio mc; do
        if [ "$component" = minio ]; then version="$MINIO_VERSION"; else version="$MC_VERSION"; fi
        for asset in "$component-$version-linux-$architecture.tar.gz" \
            "$component-$version-source-linux-$architecture.tar.gz" \
            "$component-$version-linux-$architecture-SOURCE.txt"; do
            test -s "$asset"
            test -s "$asset.sha256"
            sha256sum -c "$asset.sha256"
        done
    done
done
test "$(gh repo view "$repository" --json isPrivate --jq '.isPrivate')" = false
cat > "$output/RELEASE-NOTES.md" <<EOF
MinIO server: $MINIO_VERSION
MinIO client: $MC_VERSION
Linux architectures: ARM64 and AMD64 (CGO disabled; Alpine execution tested).
Each binary archive includes LICENSE and SOURCE.txt. Corresponding source
archives include vendored dependencies. Verify assets using .sha256 sidecars.
Production RTK releases and their existing repository are unchanged.
EOF
# Creation fails for existing release tags; never overwrite their assets.
# Upload failures leave a draft instead of a partially published release.
gh release create "$MINIO_BUNDLE_RELEASE" ./*.tar.gz ./*.sha256 ./*-SOURCE.txt \
    --repo "$repository" --draft --title "$MINIO_BUNDLE_RELEASE" --notes-file "$output/RELEASE-NOTES.md"
gh release edit "$MINIO_BUNDLE_RELEASE" --repo "$repository" --draft=false
