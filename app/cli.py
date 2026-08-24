"""Command-line entry using the same experiment engine as the UI."""

from __future__ import annotations

import json
import shutil
import sys

import click

from app.auth.blockchain.compiler import fetch_solc_windows
from app.core.config import ExperimentConfig
from app.core.constants import SCENARIOS
from app.experiments.identities import IdentityPopulation
from app.experiments.runner import (
    ExperimentRunner,
    data_dir,
    deployment_path,
    project_root,
    register_population_on_chain,
)


@click.group()
def main() -> None:
    """UAV-to-GCS authentication evaluation platform."""


@main.command("setup")
def setup_cmd() -> None:
    """Create directories and a Python reminder (venv is created by scripts)."""
    (project_root() / "var").mkdir(exist_ok=True)
    (project_root() / "results" / "runs").mkdir(parents=True, exist_ok=True)
    try:
        fetch_solc_windows()
    except Exception as exc:  # noqa: BLE001
        click.echo(f"solc download skipped: {type(exc).__name__}")
    click.echo(
        "Created var/ and results/runs/. Install deps with: python -m pip install -r requirements.txt"
    )


@main.command("besu-up")
def besu_up() -> None:
    from scripts.besu_network import up

    up()
    click.echo("Besu compose up requested.")


@main.command("besu-status")
def besu_status() -> None:
    from scripts.besu_network import status

    click.echo(json.dumps(status(), indent=2))


@main.command("besu-down")
def besu_down() -> None:
    from scripts.besu_network import down

    down()


@main.command("deploy-contract")
def deploy_contract() -> None:
    from scripts.besu_network import wait_for_block

    from app.auth.blockchain.compiler import compile_registry
    from app.auth.blockchain.registry import RegistryAdapter, save_deployment
    from app.core.constants import DEFAULT_RPC_URL

    if not wait_for_block(60):
        raise click.ClickException("Besu RPC is not producing blocks yet")
    artifact = compile_registry()
    ra_path = data_dir() / "besu" / "ra_key.json"
    if not ra_path.exists():
        raise click.ClickException("RA key missing; run besu-up / generate first")
    ra = json.loads(ra_path.read_text(encoding="utf-8"))
    adapter = RegistryAdapter(rpc_url=DEFAULT_RPC_URL, private_key=ra["private_key"], timeout_s=30)
    record = adapter.deploy()
    record["rpc_url"] = DEFAULT_RPC_URL
    record["artifact_sha256"] = artifact["bytecodeSha256"]
    record["image"] = "hyperledger/besu:26.7.1"
    save_deployment(deployment_path(), record)
    click.echo(json.dumps(record, indent=2))


@main.command("init-identities")
@click.option("--count", default=10, type=int)
@click.option("--register-on-chain/--no-register-on-chain", default=True)
def init_identities(count: int, register_on_chain: bool) -> None:
    pop = IdentityPopulation(data_dir())
    payload = pop.generate(count)
    click.echo(f"Generated {payload['count']} UAV identities (NON-PRODUCTION keys).")
    if register_on_chain and deployment_path().exists():
        receipts = register_population_on_chain(pop)
        click.echo(f"On-chain registrations/revocations: {len(receipts)}")
    elif register_on_chain:
        click.echo("Contract not deployed; skipped on-chain registration.")


@main.command("env-status")
def env_status() -> None:
    from app.ui.services import full_environment_status

    click.echo(json.dumps(full_environment_status(), indent=2, default=str))


@main.command("run")
@click.option("--mechanism", default="x509", type=click.Choice(["x509", "blockchain", "both"]))
@click.option("--scenarios", default="valid_active")
@click.option("--repetitions", default=5, type=int)
@click.option("--warmup", default=1, type=int)
@click.option("--concurrency", default="1")
@click.option("--identities", default=10, type=int)
@click.option("--confirm-large-run", is_flag=True)
@click.option("--notes", default="")
@click.option("--audit-tx", is_flag=True)
@click.option("--run-id", default="", help="Override result folder name")
def run_cmd(
    mechanism: str,
    scenarios: str,
    repetitions: int,
    warmup: int,
    concurrency: str,
    identities: int,
    confirm_large_run: bool,
    notes: str,
    audit_tx: bool,
    run_id: str,
) -> None:
    cfg = ExperimentConfig(
        mechanism=mechanism,
        scenarios=[s.strip() for s in scenarios.split(",") if s.strip()],
        repetitions=repetitions,
        warmup_repetitions=warmup,
        concurrency_levels=concurrency,
        n_identities=identities,
        confirm_large_run=confirm_large_run,
        notes=notes,
        audit_tx_enabled=audit_tx,
    )
    click.echo(cfg.to_json())
    runner = ExperimentRunner(cfg, run_id=run_id or None)
    path = runner.run()
    click.echo(f"run written to {path}")


@main.command("smoke-test")
def smoke_test() -> None:
    """X.509 smoke always; blockchain smoke if Besu+contract are available."""
    pop = IdentityPopulation(data_dir())
    if not pop.meta_path.exists():
        pop.generate(10)
    cfg = ExperimentConfig(
        mechanism="x509",
        scenarios=[
            "valid_active",
            "unknown_uav",
            "impersonation_wrong_key",
            "replay",
            "revoked_uav",
        ],
        repetitions=2,
        warmup_repetitions=1,
        concurrency_levels=[1],
        n_identities=10,
        notes="cli-smoke-x509",
        confirm_large_run=True,
    )
    path = ExperimentRunner(cfg).run()
    click.echo(f"X.509 smoke: {path}")
    from app.auth.blockchain.client import is_reachable

    if is_reachable() and deployment_path().exists():
        receipts = register_population_on_chain(pop)
        click.echo(f"On-chain identity ops: {len(receipts)}")
        cfg2 = ExperimentConfig(
            mechanism="blockchain",
            scenarios=[
                "valid_active",
                "unknown_uav",
                "impersonation_wrong_key",
                "replay",
                "revoked_uav",
            ],
            repetitions=2,
            warmup_repetitions=1,
            concurrency_levels=[1],
            n_identities=10,
            notes="cli-smoke-blockchain",
            confirm_large_run=True,
        )
        path2 = ExperimentRunner(cfg2).run()
        click.echo(f"blockchain smoke: {path2}")
    else:
        click.echo("Besu/contract unavailable; skipped blockchain smoke.")


@main.command("ui")
def ui_cmd() -> None:
    import subprocess

    app = project_root() / "streamlit_app.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app)], check=True)


@main.command("reset-local")
@click.option("--confirm", is_flag=True)
@click.option("--full", is_flag=True, help="Also stop Besu and delete generated keys/certs.")
def reset_local(confirm: bool, full: bool) -> None:
    if not confirm:
        raise click.ClickException("pass --confirm")
    root = project_root()
    for rel in ("results/runs",):
        path = root / rel
        if path.exists():
            shutil.rmtree(path)
            path.mkdir(parents=True)
    if full:
        from scripts.besu_network import reset

        reset(confirm=True)
        var = root / "var"
        if var.exists():
            for child in var.iterdir():
                if child.name == ".gitkeep":
                    continue
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
    click.echo("Local experiment data reset (project directory only).")


@main.command("list-scenarios")
def list_scenarios() -> None:
    click.echo("\n".join(SCENARIOS))


@main.command("run-chapter5")
@click.option("--dry-run", is_flag=True)
@click.option("--start-step", default=1, type=int)
@click.option(
    "--output-root",
    default=None,
    help="Root for progress + runs/ (default: results/). Use a new path for corrective re-runs.",
)
def run_chapter5(dry_run: bool, start_step: int, output_root: str | None) -> None:
    """Run the Chapter 3 workload matrix with descriptive result folder names."""
    from scripts.run_chapter5_matrix import run_matrix

    summary = run_matrix(start_step=start_step, dry_run=dry_run, output_root=output_root)
    click.echo(
        json.dumps(
            {
                "n_jobs": summary["n_jobs"],
                "dry_run": summary["dry_run"],
                "output_root": summary.get("output_root"),
            },
            indent=2,
        )
    )


@main.command("export-chapter5")
@click.option("--runs-root", default=None, help="Directory containing n*-identities_* run folders")
@click.option("--export-dir", default=None, help="Destination export directory")
def export_chapter5(runs_root: str | None, export_dir: str | None) -> None:
    """Export CSV/JSON bundle for Chapter 5 dissertation writing."""
    from scripts.export_chapter5_bundle import export_bundle

    out = export_bundle(runs_root=runs_root, export_dir=export_dir)
    click.echo(f"Exported Chapter 5 bundle to {out}")


if __name__ == "__main__":
    main()
