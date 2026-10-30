"""Offline contracts for the staged Kubernetes/Minikube release workflow."""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_stage_cluster_release_has_immutable_versions_checksums_and_two_architectures():
    source = (ROOT / "stage-cluster-tools/build-release.sh").read_text()
    pins = (ROOT / "stage-cluster-tools/releases.env").read_text()
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/stage-cluster-tools-release.yml").read_text()
    )

    assert "KUBERNETES_VERSION=v1.30.0" in pins
    assert "MINIKUBE_VERSION=v1.34.0" in pins
    assert "release/stable.txt" not in source
    assert "releases/latest" not in source
    assert source.count("sha256sum -c -") == 1
    assert 'tar -C "$preloaded_root" -czf "$root/preloaded_binaries.tar.gz" .' in source
    for checksum in (
        "7c3807c0f5c1b30110a2ff1e55da1d112a6d0096201f1beb81b269f582b5d1c5",
        "669af0cf520757298ea60a8b6eb6b719ba443a9c7d35f36d3fb2fd7513e8c7d2",
        "c4a625f9b4a4523e74b745b6aac8b0bf45062472be72cd38a23c91ec04d534c9",
        "fbe55f563ac33328320d64c319f635386fe020eedf25cba8ebf3850048deb7ae",
    ):
        assert checksum in source
    assert {entry["arch"] for entry in workflow["jobs"]["package"]["strategy"]["matrix"]["include"]} == {"arm64", "amd64"}
    assert workflow["jobs"]["publish"]["environment"] == "stage-cluster-tools-release"
    verification = workflow["jobs"]["package"]["steps"][2]["run"]
    for command in ("kubectl", "minikube", "kubelet", "kubeadm"):
        assert command in verification
    assert "alpine:3.22" in verification
    assert 'tar -xzf "$root/preloaded_binaries.tar.gz"' in verification


def test_stage_cluster_publisher_refuses_other_repositories_and_validates_both_archives():
    source = (ROOT / "stage-cluster-tools/publish-release.sh").read_text()
    assert "hplustree/prebuilt-tools" in source
    assert "for architecture in arm64 amd64" in source
    assert "sha256sum -c" in source
    assert "--draft" in source
