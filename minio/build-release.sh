#!/bin/bash
# Run only in the separate repository's explicitly dispatched release workflow.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
source "$script_dir/releases.env"
architecture="${1:?Pass arm64 or amd64}"
case "$architecture:$(uname -m)" in
    arm64:aarch64|amd64:x86_64) ;;
    *) echo "Release must be built and tested on native Linux" >&2; exit 1 ;;
esac
mkdir -p "${2:?Pass an output directory}"
output="$(cd -- "$2" && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
export CGO_ENABLED=0 GOOS=linux GOARCH="$architecture" GOTOOLCHAIN=local

for component in minio mc; do
    if [ "$component" = minio ]; then
        version="$MINIO_VERSION"; expected_commit="$MINIO_COMMIT"; flag_variable=MINIO_RELEASE
    else
        version="$MC_VERSION"; expected_commit="$MC_COMMIT"; flag_variable=MC_RELEASE
    fi
    source_dir="$work/$component-source"
    package_dir="$work/$component-package"
    repository="https://github.com/minio/$component.git"
    sh "$script_dir/clone-source.sh" "$repository" "$version" "$source_dir"
    mkdir -p "$package_dir"
    (
        cd "$source_dir"
        commit="$(git rev-parse HEAD)"
        test "$commit" = "$expected_commit"
        go mod vendor
        # Release tags record the release timestamp, not necessarily commit time.
        timestamp="${version#RELEASE.}"
        timestamp="${timestamp:0:13}:${timestamp:14:2}:${timestamp:17}"
        if [ "$component" = minio ]; then
            flags="$(MINIO_RELEASE=RELEASE go run -mod=vendor buildscripts/gen-ldflags.go "$timestamp")"
        else
            flags="$(MC_RELEASE=RELEASE go run -mod=vendor buildscripts/gen-ldflags.go "$timestamp")"
        fi
        go build -mod=vendor -p 2 -trimpath -ldflags="$flags" -o "$package_dir/$component" .
        "$package_dir/$component" --version | grep -F "$version"
        source_asset="$component-$version-source-linux-$architecture.tar.gz"
        # Include vendored dependencies and licenses, excluding Git credentials/history.
        tar --exclude=.git -czf "$output/$source_asset" .
        cp LICENSE "$package_dir/LICENSE"
        cat > "$package_dir/SOURCE.txt" <<EOF
Upstream: $repository
Upstream release: $version
Upstream commit: $commit
Source archive (including vendor dependencies): $source_asset
Source URL: https://github.com/hplustree/prebuilt-tools/releases/download/$MINIO_BUNDLE_RELEASE/$source_asset
Build scripts: https://github.com/hplustree/prebuilt-tools/tree/${GITHUB_SHA:-main}/minio
Go toolchain: $(go version)
Build: CGO_ENABLED=0 GOOS=linux GOARCH=$architecture go build -mod=vendor -p 2 -trimpath -ldflags="\$flags" -o $component .
Generate flags with: $flag_variable=RELEASE go run -mod=vendor buildscripts/gen-ldflags.go "$timestamp"
Flags: $flags
EOF
    )
    archive="$component-$version-linux-$architecture.tar.gz"
    tar -C "$package_dir" -czf "$output/$archive" "$component" LICENSE SOURCE.txt
    cp "$package_dir/SOURCE.txt" "$output/$component-$version-linux-$architecture-SOURCE.txt"
done
(
    cd "$output"
    for asset in *.tar.gz *-SOURCE.txt; do sha256sum "$asset" > "$asset.sha256"; done
)
