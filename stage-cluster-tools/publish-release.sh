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

for architecture in arm64 amd64; do
    asset="stage-cluster-tools-k8s-${KUBERNETES_VERSION}-minikube-${MINIKUBE_VERSION}-linux-${architecture}.tar.gz"
    test -s "$output/$asset"
    test -s "$output/$asset.sha256"
    (cd "$output" && sha256sum -c "$asset.sha256")
done
test "$(gh repo view "$repository" --json isPrivate --jq '.isPrivate')" = false

cat > "$output/RELEASE-NOTES.md" <<EOF
Checksum-verified Kubernetes $KUBERNETES_VERSION and Minikube $MINIKUBE_VERSION
binaries for ARM64 and AMD64. Each archive contains kubectl, minikube, and the
preloaded kubectl/kubelet/kubeadm cache used by the stage-cluster image.

These are repackaged official upstream release artifacts. See each archive's
SOURCE.txt for immutable source URLs, licenses, and upstream SHA-256 values.
EOF

# Never overwrite a release; an upload failure leaves a draft for inspection.
cd "$output"
gh release create "$STAGE_CLUSTER_TOOLS_RELEASE" ./*.tar.gz ./*.sha256 \
    --repo "$repository" --draft --title "$STAGE_CLUSTER_TOOLS_RELEASE" \
    --notes-file RELEASE-NOTES.md
gh release edit "$STAGE_CLUSTER_TOOLS_RELEASE" --repo "$repository" --draft=false
