#!/bin/bash
# Package checksum-verified upstream Kubernetes and Minikube binaries. This
# script intentionally downloads official release artifacts; it does not build
# or modify either upstream project.
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
source "$script_dir/releases.env"
architecture="${1:?Pass arm64 or amd64}"
output="${2:?Pass output directory}"

case "$architecture" in
    arm64)
        kubectl_sha256=669af0cf520757298ea60a8b6eb6b719ba443a9c7d35f36d3fb2fd7513e8c7d2
        kubelet_sha256=fa887647422d34f3c7cc5b30fefcf97084d2c3277eff237c5808685ba8e4b15a
        kubeadm_sha256=c36afd28921303e6db8e58274de16c60a80a1e75030fc3c4e9c4ed6249b6b696
        minikube_sha256=fbe55f563ac33328320d64c319f635386fe020eedf25cba8ebf3850048deb7ae
        ;;
    amd64)
        kubectl_sha256=7c3807c0f5c1b30110a2ff1e55da1d112a6d0096201f1beb81b269f582b5d1c5
        kubelet_sha256=32a32ec3d7e7f8b2648c9dd503ce9ef63b4af1d1677f5b5aed7846fb02d66f18
        kubeadm_sha256=29f4232c50e6524abba3443ff3b9948d386964d79eb8dfefb409e1f8a8434c14
        minikube_sha256=c4a625f9b4a4523e74b745b6aac8b0bf45062472be72cd38a23c91ec04d534c9
        ;;
    *) echo "Unsupported architecture: $architecture" >&2; exit 1 ;;
esac

mkdir -p "$output"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
bundle="stage-cluster-tools-k8s-${KUBERNETES_VERSION}-minikube-${MINIKUBE_VERSION}-linux-${architecture}"
root="$work/$bundle"
preloaded_root="$work/preloaded_binaries"
preloaded="$preloaded_root/linux/$architecture/$KUBERNETES_VERSION"
mkdir -p "$root/bin" "$preloaded"

download() {
    local url="$1" destination="$2" checksum="$3"
    curl --fail --location --silent --show-error --retry 3 --retry-delay 2 --connect-timeout 15 \
        "$url" -o "$destination"
    echo "$checksum  $destination" | sha256sum -c -
}

kubernetes_base="https://dl.k8s.io/release/${KUBERNETES_VERSION}/bin/linux/${architecture}"
download "$kubernetes_base/kubectl" "$root/bin/kubectl" "$kubectl_sha256"
download "https://github.com/kubernetes/minikube/releases/download/v${MINIKUBE_VERSION}/minikube-linux-${architecture}" \
    "$root/bin/minikube" "$minikube_sha256"
cp "$root/bin/kubectl" "$preloaded/kubectl"
download "$kubernetes_base/kubelet" "$preloaded/kubelet" "$kubelet_sha256"
download "$kubernetes_base/kubeadm" "$preloaded/kubeadm" "$kubeadm_sha256"
chmod 0755 "$root/bin/"* "$preloaded/"*
# Keep the inner archive layout identical to the file the stage-cluster image
# extracts into /root/.minikube/cache: its root is linux/, not a bundle folder.
tar -C "$preloaded_root" -czf "$root/preloaded_binaries.tar.gz" .

cat > "$root/SOURCE.txt" <<EOF
Stage-cluster tool bundle: $STAGE_CLUSTER_TOOLS_RELEASE
Kubernetes version: $KUBERNETES_VERSION
Minikube version: $MINIKUBE_VERSION
Architecture: $architecture

Upstream Kubernetes binaries:
$kubernetes_base/{kubectl,kubelet,kubeadm}
Source: https://github.com/kubernetes/kubernetes (Apache-2.0)

Upstream Minikube binary:
https://github.com/kubernetes/minikube/releases/download/v${MINIKUBE_VERSION}/minikube-linux-${architecture}
Source: https://github.com/kubernetes/minikube (Apache-2.0)

Checksums verified before packaging:
kubectl  $kubectl_sha256
kubelet  $kubelet_sha256
kubeadm  $kubeadm_sha256
minikube $minikube_sha256
EOF

tar -C "$work" -czf "$output/$bundle.tar.gz" "$bundle"
(cd "$output" && sha256sum "$bundle.tar.gz" > "$bundle.tar.gz.sha256")
