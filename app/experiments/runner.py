"""Experiment engine shared by the CLI and Streamlit UI."""

from __future__ import annotations

import csv
import json
import os
import platform
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.auth.blockchain.adapter import BlockchainIdentityBackend
from app.auth.blockchain.client import chain_status
from app.auth.blockchain.registry import RegistryAdapter
from app.auth.common.protocol import GCSAuthService
from app.auth.x509.adapter import X509IdentityBackend, load_roles
from app.core.canonical import payload_digest_hex
from app.core.config import ExperimentConfig
from app.core.constants import DEFAULT_RPC_URL
from app.core.schemas import Observation
from app.experiments.identities import SPECIAL_IDS, IdentityPopulation
from app.experiments.sampler import ResourceSampler
from app.experiments.scenarios import mixed_kind, prepare_attempt
from app.metrics.charts import write_charts
from app.metrics.summary import summarise_observations, summary_csv_rows
from app.storage.artifacts import RunStore


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    override = os.environ.get("UAV_AUTH_DATA_DIR")
    return Path(override) if override else project_root() / "var"


def results_root() -> Path:
    override = os.environ.get("UAV_AUTH_RESULTS_DIR")
    return Path(override) if override else project_root() / "results" / "runs"


def deployment_path() -> Path:
    return data_dir() / "deployment.json"


def environment_metadata() -> dict[str, Any]:
    import cryptography
    import pandas
    import psutil
    import web3

    import app as pkg

    vm = psutil.virtual_memory()
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "total_memory_bytes": vm.total,
        "package_versions": {
            "uav-auth-eval": pkg.__version__,
            "cryptography": cryptography.__version__,
            "web3": web3.__version__,
            "pandas": pandas.__version__,
            "psutil": psutil.__version__,
        },
        "captured_at": datetime.now(UTC).isoformat(),
    }


def make_x509_service(cfg: ExperimentConfig, pop: IdentityPopulation) -> GCSAuthService:
    from app.core.nonce import NonceStore

    roles = load_roles(pop.roles_path)
    backend = X509IdentityBackend(pop.pki, roles)
    return GCSAuthService(
        backend=backend,
        nonce_store=NonceStore(),
        gcs_id=cfg.gcs_id,
        challenge_lifetime_s=cfg.challenge_lifetime_s,
    )


def make_blockchain_service(cfg: ExperimentConfig, rpc_url: str | None = None) -> GCSAuthService:
    from app.core.nonce import NonceStore

    dep = {}
    if deployment_path().exists():
        dep = json.loads(deployment_path().read_text(encoding="utf-8"))
    url = rpc_url or dep.get("rpc_url") or DEFAULT_RPC_URL
    adapter = RegistryAdapter(
        rpc_url=url,
        address=dep.get("address"),
        private_key=_load_ra_key(),
        timeout_s=cfg.rpc_timeout_s,
        confirmation_blocks=cfg.confirmation_blocks,
    )
    backend = BlockchainIdentityBackend(adapter, audit_tx=cfg.audit_tx_enabled)
    return GCSAuthService(
        backend=backend,
        nonce_store=NonceStore(),
        gcs_id=cfg.gcs_id,
        challenge_lifetime_s=cfg.challenge_lifetime_s,
    )


def make_rpc_down_service(cfg: ExperimentConfig) -> GCSAuthService:
    from app.core.nonce import NonceStore

    adapter = RegistryAdapter(
        rpc_url="http://127.0.0.1:1",
        address="0x0000000000000000000000000000000000000001",
        timeout_s=min(1.0, cfg.rpc_timeout_s),
        confirmation_blocks=1,
    )
    # Force a contract object so lookup attempts eth_call and fails closed.
    try:
        adapter._contract = adapter.w3.eth.contract(
            address=adapter.address, abi=adapter.artifact["abi"]
        )
    except Exception:  # noqa: BLE001
        pass
    backend = BlockchainIdentityBackend(adapter, audit_tx=False)
    return GCSAuthService(
        backend=backend,
        nonce_store=NonceStore(),
        gcs_id=cfg.gcs_id,
        challenge_lifetime_s=cfg.challenge_lifetime_s,
    )


def _load_ra_key() -> str | None:
    path = data_dir() / "besu" / "ra_key.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("private_key")


class ExperimentRunner:
    def __init__(
        self,
        cfg: ExperimentConfig,
        *,
        run_id: str | None = None,
        on_status: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.cfg = cfg
        self.run_id = run_id or cfg.descriptive_run_id()
        self.on_status = on_status
        self.pop = IdentityPopulation(data_dir())
        self.store: RunStore | None = None
        self._counts = {
            "completed": 0,
            "accepted": 0,
            "expected_rejection": 0,
            "unexpected": 0,
            "timeout": 0,
            "internal": 0,
        }
        self._total = cfg.estimate_total_requests()
        self._started = 0.0
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()
        if self.store:
            self.store.request_cancel()

    def run(self) -> Path:
        out_root = Path(self.cfg.output_dir)
        if not out_root.is_absolute():
            out_root = project_root() / out_root
        run_dir = out_root / self.run_id
        if run_dir.exists() and (run_dir / "checksums.sha256").exists():
            raise RuntimeError(f"refusing to overwrite completed run {run_dir}")
        index = data_dir() / "runs_index.sqlite"
        self.store = RunStore(run_dir, index_db=index)
        self.store.write_json("config.json", self.cfg.to_dict())
        env = environment_metadata()
        env["besu"] = chain_status()
        env["deployment"] = (
            json.loads(deployment_path().read_text(encoding="utf-8"))
            if deployment_path().exists()
            else {}
        )
        env["pki"] = self.pop.pki.status() if (data_dir() / "pki").exists() else {}
        env["identities"] = self.pop.comparable_summary()
        self.store.write_json("environment.json", env)
        self.store.append_event({"type": "run_start", "run_id": self.run_id})
        self.store.upsert_index(self.run_id, "running", self.cfg.mechanism, self.cfg.notes, 0)
        sampler = ResourceSampler(self.cfg.resource_sample_interval_s, self.store.append_metric_row)
        sampler.start()
        self._started = time.perf_counter()
        payload = os.urandom(self.cfg.payload_size) if self.cfg.payload_size else b""
        digest = payload_digest_hex(payload)
        try:
            for mechanism in self.cfg.mechanisms():
                if self._stop():
                    break
                for scenario in self.cfg.applicable_scenarios(mechanism):
                    if self._stop():
                        break
                    for conc in self.cfg.concurrency_levels:
                        if self._stop():
                            break
                        self._run_batch(mechanism, scenario, conc, digest)
        finally:
            sampler.stop()
        status_name = "cancelled" if self._stop() else "completed"
        observations = []
        obs_path = self.store.obs_path
        if obs_path.exists():
            with obs_path.open(newline="", encoding="utf-8") as fh:
                observations = list(csv.DictReader(fh))
        elapsed = max(time.perf_counter() - self._started, 1e-9)
        offered = self._counts["completed"] / elapsed if elapsed else None
        summary = summarise_observations(
            observations,
            seed=self.cfg.random_seed,
            batch_seconds=elapsed,
            offered_load=offered,
        )
        self.store.write_json("summary.json", summary)
        with (self.store.run_dir / "summary.csv").open("w", newline="", encoding="utf-8") as fh:
            rows = summary_csv_rows(summary, self.run_id)
            if rows:
                writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
        write_charts(observations, self.store.charts_dir)
        self.store.append_event({"type": "run_end", "status": status_name})
        payload_status = {
            "run_id": self.run_id,
            "status": status_name,
            "completed": self._counts["completed"],
            "total": self._total,
            "counts": self._counts,
            "elapsed_s": elapsed,
        }
        self.store.write_status(payload_status)
        self.store.upsert_index(
            self.run_id, status_name, self.cfg.mechanism, self.cfg.notes, self._counts["completed"]
        )
        self.store.finalise_checksums()
        return self.store.run_dir

    def _stop(self) -> bool:
        return self._cancel.is_set() or (self.store.cancelled() if self.store else False)

    def _service_for(self, mechanism: str, scenario: str) -> GCSAuthService:
        if mechanism == "x509":
            return make_x509_service(self.cfg, self.pop)
        if scenario == "rpc_unavailable":
            return make_rpc_down_service(self.cfg)
        return make_blockchain_service(self.cfg)

    def _run_batch(self, mechanism: str, scenario: str, conc: int, digest: str) -> None:
        warmup = self.cfg.warmup_repetitions if conc == self.cfg.concurrency_levels[0] else 0
        measured = int(self.cfg.requests_per_concurrency or self.cfg.repetitions)
        jobs = [("warmup", i) for i in range(warmup)] + [("meas", i) for i in range(measured)]
        service = self._service_for(mechanism, scenario)

        def execute(kind: str, idx: int) -> Observation | None:
            if self._stop():
                return None
            scen = mixed_kind(idx) if scenario == "concurrent_mixed" else scenario
            worker = threading.current_thread().name
            from app.core.schemas import AuthDecision, Timings

            t_auth0 = time.perf_counter()
            try:
                prepared = prepare_attempt(
                    service,
                    self.pop,
                    scen,
                    self.cfg.requested_operation,
                    digest,
                    mechanism,
                    self.cfg.challenge_lifetime_s,
                )
                decision = service.authenticate(prepared.request)
                if mechanism == "blockchain" and self.cfg.audit_tx_enabled:
                    audit = service.backend.maybe_audit(prepared.uav_id, decision.outcome)
                    if audit and self.store:
                        decision.tx_hash = str(audit.get("tx_hash") or "")
                        decision.block_number = str(audit.get("block_number") or "")
                        decision.gas_used = str(audit.get("gas_used") or "")
                        decision.timings.audit_submission_ns = int(audit.get("submit_ns") or 0)
                        decision.timings.audit_confirmation_ns = int(audit.get("confirm_ns") or 0)
                        self.store.append_receipt({"scenario": scen, **audit})
                if time.perf_counter() - t_auth0 > self.cfg.auth_timeout_s:
                    decision.timeout_error_class = "auth_timeout"
            except Exception as exc:  # noqa: BLE001
                prepared = type(
                    "P",
                    (),
                    {
                        "expected": "INTERNAL_ERROR",
                        "uav_id": "?",
                        "challenge_generation_ns": 0,
                        "notes": type(exc).__name__,
                    },
                )()
                decision = AuthDecision(
                    outcome="INTERNAL_ERROR",
                    reason_detail=type(exc).__name__,
                    timings=Timings(),
                    timeout_error_class="internal",
                )
            decision.timings.challenge_generation_ns = getattr(
                prepared, "challenge_generation_ns", 0
            )
            if mechanism == "blockchain" and decision.timings.contract_call_ns == 0:
                decision.timings.contract_call_ns = decision.timings.identity_lookup_ns
            return Observation.from_decision(
                run_id=self.run_id,
                mechanism=mechanism,
                scenario=scenario if scenario != "concurrent_mixed" else scen,
                repetition=idx,
                concurrency_level=conc,
                uav_id=prepared.uav_id,
                expected_outcome=prepared.expected,
                decision=decision,
                worker_id=worker,
                payload_size=self.cfg.payload_size,
                warmup=(kind == "warmup"),
                notes=getattr(prepared, "notes", ""),
            )

        workers = max(1, conc)
        with ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix=f"{mechanism}-{scenario}"
        ) as pool:
            futures = [pool.submit(execute, kind, idx) for kind, idx in jobs]
            for fut in as_completed(futures):
                obs = fut.result()
                if obs is None:
                    continue
                assert self.store is not None
                self.store.append_observation(obs)
                self._counts["completed"] += 1
                if obs.observed_outcome == "ACCEPTED":
                    self._counts["accepted"] += 1
                elif obs.expectation_met:
                    self._counts["expected_rejection"] += 1
                else:
                    self._counts["unexpected"] += 1
                if obs.timeout_error_class not in {"none", ""}:
                    self._counts["timeout"] += 1
                if obs.observed_outcome == "INTERNAL_ERROR":
                    self._counts["internal"] += 1
                self._publish(mechanism, scenario, conc)

    def _publish(self, mechanism: str, scenario: str, conc: int) -> None:
        elapsed = time.perf_counter() - self._started
        done = self._counts["completed"]
        remaining = None
        if done:
            rate = done / max(elapsed, 1e-9)
            remaining = max(self._total - done, 0) / rate if rate else None
        payload = {
            "run_id": self.run_id,
            "status": "cancelled" if self._stop() else "running",
            "mechanism": mechanism,
            "scenario": scenario,
            "concurrency_level": conc,
            "completed": done,
            "total": self._total,
            "elapsed_s": elapsed,
            "eta_s": remaining,
            "counts": dict(self._counts),
        }
        if self.store:
            self.store.write_status(payload)
            self.store.append_event({"type": "progress", **payload})
        if self.on_status:
            self.on_status(payload)


def register_population_on_chain(pop: IdentityPopulation) -> list[dict[str, Any]]:
    """Register or synchronise local UAV public keys onto the registry.

    If an identity is already Active/Suspended but the on-chain public key does
    not match the local signing key, call ``updateKey`` (and ``updateRole`` when
    needed) for identities used in authentication scenarios. Skipping this sync
    leaves stale keys after local identity regeneration and causes systematic
    ``INVALID_SIGNATURE`` false rejections. Bulk non-scenario identities are
    registered when missing but not mass-updated, to avoid overwhelming local
    Besu during the matrix.
    """
    if not deployment_path().exists():
        raise RuntimeError("contract is not deployed; run deploy-contract first")
    dep = json.loads(deployment_path().read_text(encoding="utf-8"))
    adapter = RegistryAdapter(
        rpc_url=dep.get("rpc_url") or DEFAULT_RPC_URL,
        address=dep["address"],
        private_key=_load_ra_key(),
        timeout_s=30,
    )
    receipts = []
    specials = set(SPECIAL_IDS)
    for rec in pop.load_meta().get("identities", []):
        uav_id = rec["uav_id"]
        pk = bytes.fromhex(rec["public_key_hex"])
        role = int(rec["role"])
        existing = _get_record_retry(adapter, uav_id)
        status = int(existing["status"])
        if status == 0:
            receipts.append(
                {"uav_id": uav_id, "op": "register", **adapter.register(uav_id, pk, role)}
            )
            existing = _get_record_retry(adapter, uav_id)
            status = int(existing["status"])
        elif status in {1, 2} and uav_id in specials:
            chain_pk = bytes(existing["public_key"] or b"")
            if chain_pk != pk:
                receipts.append(
                    {"uav_id": uav_id, "op": "updateKey", **adapter.update_key(uav_id, pk)}
                )
            if int(existing["role"]) != role:
                receipts.append(
                    {"uav_id": uav_id, "op": "updateRole", **adapter.update_role(uav_id, role)}
                )
        if "revoked" in rec.get("tags", []) and status != 3:
            existing = _get_record_retry(adapter, uav_id)
            status = int(existing["status"])
            if status in {1, 2}:
                receipts.append({"uav_id": uav_id, "op": "revoke", **adapter.revoke(uav_id)})
    return receipts


def _get_record_retry(adapter: RegistryAdapter, uav_id: str, attempts: int = 5) -> dict[str, Any]:
    import time

    last: Exception | None = None
    for i in range(attempts):
        try:
            return adapter.get_record(uav_id)
        except Exception as exc:  # noqa: BLE001 — Besu transient Internal error
            last = exc
            time.sleep(0.4 * (i + 1))
    assert last is not None
    raise last
