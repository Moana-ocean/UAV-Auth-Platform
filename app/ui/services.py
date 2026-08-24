"""Service helpers used by Streamlit (no protocol logic in callbacks)."""

from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Any

import psutil

from app.auth.blockchain.client import chain_status, is_reachable, load_deployment
from app.auth.blockchain.compiler import load_artifact, source_path
from app.core.constants import BESU_IMAGE, CHAIN_ID
from app.experiments.identities import IdentityPopulation
from app.experiments.runner import data_dir, deployment_path, environment_metadata, project_root
from app.storage.artifacts import list_runs, read_observations, zip_run


def full_environment_status() -> dict[str, Any]:
    pop = IdentityPopulation(data_dir())
    pki = {}
    try:
        pki = pop.pki.status()
    except Exception as exc:  # noqa: BLE001
        pki = {"error": type(exc).__name__}
    dep = load_deployment(deployment_path())
    artifact = {}
    try:
        if (project_root() / "contracts" / "artifacts" / "UAVIdentityRegistry.json").exists():
            art = load_artifact()
            artifact = {
                "source": str(source_path()),
                "source_sha256": art.get("sourceSha256"),
                "bytecode_sha256": art.get("bytecodeSha256"),
                "solc": art.get("solcVersion"),
            }
    except Exception as exc:  # noqa: BLE001
        artifact = {"error": type(exc).__name__}
    docker_ok = False
    try:
        import subprocess

        docker_ok = subprocess.run(["docker", "version"], capture_output=True).returncode == 0
    except Exception:  # noqa: BLE001
        docker_ok = False
    warnings = []
    if not docker_ok:
        warnings.append("Docker is not available; Besu integration cannot run.")
    if not is_reachable():
        warnings.append("Besu RPC http://127.0.0.1:8545 is not reachable.")
    if not dep:
        warnings.append("Registry contract is not deployed.")
    if not pop.meta_path.exists():
        warnings.append("UAV identity population has not been generated.")
    vm = psutil.virtual_memory()
    return {
        "python": platform.python_version(),
        "os": platform.platform(),
        "cpu": platform.processor(),
        "cpu_count": psutil.cpu_count(),
        "total_memory_bytes": vm.total,
        "packages": environment_metadata().get("package_versions"),
        "docker": docker_ok,
        "besu_image": BESU_IMAGE,
        "chain_id_expected": CHAIN_ID,
        "besu_nodes": {
            "validator1": chain_status("http://127.0.0.1:8545"),
            "validator2": chain_status("http://127.0.0.1:8555"),
            "validator3": chain_status("http://127.0.0.1:8565"),
            "validator4": chain_status("http://127.0.0.1:8575"),
        },
        "deployment": dep,
        "artifact": artifact,
        "pki": pki,
        "identities": pop.comparable_summary() if pop.meta_path.exists() else {},
        "warnings": warnings,
        "topology_note": (
            "Four validator containers on one host. This is not organisational or "
            "geographic decentralisation and does not demonstrate BFT."
        ),
    }


def generate_identities(count: int, register: bool) -> dict[str, Any]:
    pop = IdentityPopulation(data_dir())
    payload = pop.generate(count)
    chain = []
    if register and deployment_path().exists():
        from app.experiments.runner import register_population_on_chain

        chain = register_population_on_chain(pop)
    return {"identities": payload["count"], "chain_ops": len(chain)}


def comparable_population() -> dict[str, Any]:
    pop = IdentityPopulation(data_dir())
    summary = pop.comparable_summary()
    on_chain = None
    if deployment_path().exists() and is_reachable():
        from app.auth.blockchain.registry import RegistryAdapter
        from app.core.constants import DEFAULT_RPC_URL
        from app.experiments.runner import _load_ra_key

        dep = json.loads(deployment_path().read_text(encoding="utf-8"))
        adapter = RegistryAdapter(DEFAULT_RPC_URL, dep.get("address"), _load_ra_key())
        active = 0
        revoked = 0
        for rec in pop.load_meta().get("identities", []):
            r = adapter.get_record(rec["uav_id"])
            if r["status"] == 1:
                active += 1
            if r["status"] == 3:
                revoked += 1
        on_chain = {"active": active, "revoked": revoked, "listed": summary.get("count")}
    return {"x509": summary, "blockchain": on_chain}


def run_history() -> list[dict[str, Any]]:
    return list_runs(project_root() / "results" / "runs")


def observations_for(run_id: str) -> list[dict[str, Any]]:
    return read_observations(project_root() / "results" / "runs" / run_id)


def export_zip(run_id: str) -> Path:
    return zip_run(project_root() / "results" / "runs" / run_id)
