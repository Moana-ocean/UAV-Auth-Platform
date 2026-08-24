"""Generate Besu QBFT keys/genesis, start/stop/reset the local four-node network."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from app.core.constants import BESU_IMAGE, CHAIN_ID, TEST_KEY_WARNING

ROOT = Path(__file__).resolve().parents[1]
BESU = ROOT / "besu"
NETWORK = BESU / "network"
CONFIG = BESU / "config" / "qbftConfigFile.json"


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, **kwargs)


def docker_available() -> bool:
    try:
        subprocess.run(["docker", "version"], check=True, capture_output=True)
        return True
    except Exception:  # noqa: BLE001
        return False


def generate_network() -> dict:
    NETWORK.mkdir(parents=True, exist_ok=True)
    tmp = BESU / "tmp"
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shutil.copy(CONFIG, tmp / "qbftConfigFile.json")
    subprocess.run(["docker", "rm", "-f", "uav-besu-genesis"], capture_output=True)
    gen = subprocess.run(
        [
            "docker",
            "run",
            "--name",
            "uav-besu-genesis",
            "-v",
            f"{tmp}:/in:ro",
            "--entrypoint",
            "/bin/bash",
            BESU_IMAGE,
            "-c",
            "/opt/besu/bin/besu operator generate-blockchain-config "
            "--config-file=/in/qbftConfigFile.json --to=/tmp/networkFiles "
            "--private-key-file-name=key",
        ],
        capture_output=True,
        text=True,
    )
    try:
        if gen.returncode != 0:
            raise RuntimeError(gen.stderr or gen.stdout or "besu operator failed")
        subprocess.run(
            ["docker", "cp", "uav-besu-genesis:/tmp/networkFiles", str(tmp / "networkFiles")],
            check=True,
        )
    finally:
        subprocess.run(["docker", "rm", "-f", "uav-besu-genesis"], capture_output=True)
    generated = tmp / "networkFiles"
    genesis = json.loads((generated / "genesis.json").read_text(encoding="utf-8"))
    keys_root = generated / "keys"
    key_dirs = sorted([p for p in keys_root.iterdir() if p.is_dir()])
    if len(key_dirs) != 4:
        raise RuntimeError(f"expected 4 validator key directories, got {len(key_dirs)}")

    from eth_account import Account

    Account.enable_unaudited_hdwallet_features()
    ra = Account.create()
    alloc = genesis.setdefault("alloc", {})
    alloc[ra.address] = {
        "balance": "0x200000000000000000000000000000000000000000000000000000000000000"
    }
    genesis.setdefault("config", {})["chainId"] = CHAIN_ID
    genesis["config"].setdefault("berlinBlock", 0)
    genesis["config"].setdefault("londonBlock", 0)
    genesis["config"].setdefault("shanghaiTime", 0)
    NETWORK.mkdir(parents=True, exist_ok=True)
    (NETWORK / "genesis.json").write_text(json.dumps(genesis, indent=2), encoding="utf-8")

    enodes = []
    validators = []
    for idx, kdir in enumerate(key_dirs, start=1):
        dest = NETWORK / f"validator{idx}"
        dest.mkdir(parents=True, exist_ok=True)
        key_src = kdir / "key" if (kdir / "key").exists() else kdir / "key.priv"
        shutil.copy(key_src, dest / "key")
        pub_path = kdir / "key.pub"
        pub_hex = ""
        if pub_path.exists():
            shutil.copy(pub_path, dest / "key.pub")
            pub_hex = pub_path.read_text(encoding="utf-8").strip().replace("0x", "")
            if pub_hex.startswith("04") and len(pub_hex) == 130:
                pub_hex = pub_hex[2:]
        host = f"172.28.45.{10 + idx}"
        if pub_hex:
            enodes.append(f"enode://{pub_hex}@{host}:30303")
        validators.append({"name": f"validator{idx}", "address": kdir.name, "dir": str(dest)})

    (NETWORK / "static-nodes.json").write_text(json.dumps(enodes, indent=2), encoding="utf-8")
    ra_dir = ROOT / "var" / "besu"
    ra_dir.mkdir(parents=True, exist_ok=True)
    ra_record = {
        "address": ra.address,
        "private_key": ra.key.hex(),
        "warning": TEST_KEY_WARNING,
    }
    (ra_dir / "ra_key.json").write_text(json.dumps(ra_record, indent=2), encoding="utf-8")
    meta = {
        "warning": "RESEARCH/TESTING ONLY. Local four-process QBFT; not BFT evidence.",
        "chain_id": CHAIN_ID,
        "image": BESU_IMAGE,
        "validators": validators,
        "enodes": enodes,
        "ra_address": ra.address,
        "ra_key_path": str((ra_dir / "ra_key.json").as_posix()),
    }
    (NETWORK / "network-meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    return meta


def compose(args: list[str]) -> None:
    cmd = ["docker", "compose", "-f", str(BESU / "docker-compose.yml"), *args]
    _run(cmd, cwd=str(BESU))


def up() -> None:
    if not (NETWORK / "genesis.json").exists():
        generate_network()
    compose(["up", "-d", "--force-recreate"])


def down() -> None:
    compose(["down"])


def status() -> dict:
    from app.auth.blockchain.client import chain_status

    nodes = {}
    for name, port in (
        ("validator1", 8545),
        ("validator2", 8555),
        ("validator3", 8565),
        ("validator4", 8575),
    ):
        nodes[name] = chain_status(f"http://127.0.0.1:{port}")
    return {
        "docker": docker_available(),
        "image": BESU_IMAGE,
        "genesis_present": (NETWORK / "genesis.json").exists(),
        "warning": "Local co-located validators; not geographically decentralised; BFT not tested.",
        "nodes": nodes,
    }


def reset(confirm: bool = False) -> None:
    if not confirm:
        raise SystemExit("refusing reset without confirm=True")
    down()
    compose(["down", "-v"])
    if NETWORK.exists():
        shutil.rmtree(NETWORK)
    data = ROOT / "var" / "besu"
    if data.exists():
        shutil.rmtree(data)
    dep = ROOT / "var" / "deployment.json"
    if dep.exists():
        dep.unlink()


def wait_for_block(timeout_s: float = 90.0) -> bool:
    from app.auth.blockchain.client import connect

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            w3 = connect("http://127.0.0.1:8545", timeout_s=2)
            if w3.is_connected() and w3.eth.block_number >= 0:
                return True
        except Exception:  # noqa: BLE001
            time.sleep(2)
            continue
        time.sleep(2)
    return False


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python -m scripts.besu_network [generate|up|down|status|reset|wait]")
        return 1
    cmd = argv[0]
    if cmd == "generate":
        print(json.dumps(generate_network(), indent=2))
        return 0
    if cmd == "up":
        up()
        return 0
    if cmd == "down":
        down()
        return 0
    if cmd == "status":
        print(json.dumps(status(), indent=2))
        return 0
    if cmd == "wait":
        ok = wait_for_block()
        print("ready" if ok else "timeout")
        return 0 if ok else 2
    if cmd == "reset":
        if "--confirm" not in argv:
            print("pass --confirm to reset the local Besu network and RA key")
            return 1
        reset(confirm=True)
        return 0
    print(f"unknown command {cmd}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
