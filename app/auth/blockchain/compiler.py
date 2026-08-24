"""Compile UAVIdentityRegistry.sol with pinned solc (local binary, Docker, then py-solc-x)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from app.core.constants import SOLC_VERSION
from app.core.crypto import sha256_hex

CONTRACT_NAME = "UAVIdentityRegistry"
SOLC_IMAGE = f"ethereum/solc:{SOLC_VERSION}"


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def source_path() -> Path:
    return project_root() / "contracts" / "contracts" / f"{CONTRACT_NAME}.sol"


def artifact_dir() -> Path:
    path = project_root() / "contracts" / "artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _normalise_bin(value: str) -> str:
    if value.startswith("0x"):
        return value[2:]
    return value


def _artifact_from_compiled(source: str, abi, bytecode: str, deployed: str) -> dict:
    raw_bin = _normalise_bin(bytecode)
    abi_obj = abi if not isinstance(abi, str) else json.loads(abi)
    return {
        "contractName": CONTRACT_NAME,
        "sourcePath": str(source_path().as_posix()),
        "solcVersion": SOLC_VERSION,
        "abi": abi_obj,
        "bytecode": bytecode if str(bytecode).startswith("0x") else "0x" + bytecode,
        "deployedBytecode": deployed if str(deployed).startswith("0x") else "0x" + deployed,
        "sourceSha256": sha256_hex(source.encode("utf-8")),
        "bytecodeSha256": sha256_hex(bytes.fromhex(raw_bin)),
        "compiler": None,
    }


def _compile_docker() -> dict:
    src = source_path()
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{src.parent.resolve()}:/src",
        SOLC_IMAGE,
        "--optimize",
        "--optimize-runs",
        "200",
        "--combined-json",
        "abi,bin,bin-runtime",
        f"/src/{src.name}",
    ]
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    payload = json.loads(proc.stdout)
    contracts = payload.get("contracts", {})
    key = next(k for k in contracts if k.endswith(CONTRACT_NAME))
    data = contracts[key]
    artifact = _artifact_from_compiled(
        src.read_text(encoding="utf-8"), data["abi"], data["bin"], data.get("bin-runtime", "")
    )
    artifact["compiler"] = SOLC_IMAGE
    return artifact


def _compile_solcx() -> dict:
    from solcx import compile_source, install_solc, set_solc_version

    install_solc(SOLC_VERSION)
    set_solc_version(SOLC_VERSION)
    source = source_path().read_text(encoding="utf-8")
    compiled = compile_source(
        source,
        output_values=["abi", "bin", "bin-runtime"],
        solc_version=SOLC_VERSION,
        optimize=True,
        optimize_runs=200,
    )
    key = f"<stdin>:{CONTRACT_NAME}"
    if key not in compiled:
        key = next(k for k in compiled if k.endswith(CONTRACT_NAME))
    data = compiled[key]
    artifact = _artifact_from_compiled(source, data["abi"], data["bin"], data["bin-runtime"])
    artifact["compiler"] = f"solcx:{SOLC_VERSION}"
    return artifact


def _compile_local_binary() -> dict:
    candidates = [
        shutil.which("solc"),
        str(project_root() / "var" / "tools" / "solc-windows.exe"),
        str(project_root() / "var" / "tools" / "solc"),
    ]
    exe = next((Path(p) for p in candidates if p and Path(p).exists()), None)
    if exe is None:
        raise FileNotFoundError("solc binary not found")
    src = source_path()
    proc = subprocess.run(
        [
            str(exe),
            "--optimize",
            "--optimize-runs",
            "200",
            "--combined-json",
            "abi,bin,bin-runtime",
            str(src),
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=str(src.parent),
    )
    payload = json.loads(proc.stdout)
    contracts = payload.get("contracts", {})
    key = next(k for k in contracts if k.endswith(CONTRACT_NAME))
    data = contracts[key]
    artifact = _artifact_from_compiled(
        src.read_text(encoding="utf-8"), data["abi"], data["bin"], data.get("bin-runtime", "")
    )
    artifact["compiler"] = str(exe)
    return artifact


def compile_registry(optimize: bool = True) -> dict:
    errors: list[str] = []
    artifact = None
    try:
        artifact = _compile_local_binary()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"local solc: {type(exc).__name__}: {exc}")
    if artifact is None and shutil.which("docker"):
        try:
            artifact = _compile_docker()
        except Exception as extra:  # noqa: BLE001
            errors.append(f"docker solc: {type(extra).__name__}: {extra}")
    if artifact is None:
        try:
            artifact = _compile_solcx()
        except Exception as extra:  # noqa: BLE001
            errors.append(f"solcx: {type(extra).__name__}: {extra}")
    if artifact is None:
        raise RuntimeError("Unable to compile contract. " + " | ".join(errors))
    out = artifact_dir() / f"{CONTRACT_NAME}.json"
    out.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return artifact


def fetch_solc_windows() -> Path:
    """Download the pinned Windows solc binary into var/tools (non-production toolchain)."""
    dest_dir = project_root() / "var" / "tools"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "solc-windows.exe"
    if dest.exists() and dest.stat().st_size > 1_000_000:
        return dest
    url = f"https://github.com/ethereum/solidity/releases/download/v{SOLC_VERSION}/solc-windows.exe"
    subprocess.run(["curl", "-L", "-o", str(dest), url], check=True)
    return dest


def load_artifact() -> dict:
    path = artifact_dir() / f"{CONTRACT_NAME}.json"
    if not path.exists():
        return compile_registry()
    return json.loads(path.read_text(encoding="utf-8"))
