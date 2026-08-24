"""Compile-only contract test (no chain)."""

from app.auth.blockchain.compiler import compile_registry, source_path


def test_contract_source_exists():
    assert source_path().exists()


def test_compile_registry():
    artifact = compile_registry()
    assert artifact["abi"]
    assert artifact["bytecode"]
    assert artifact["sourceSha256"]
    names = {item.get("name") for item in artifact["abi"] if item.get("type") == "function"}
    for required in ("register", "revoke", "updateKey", "updateRole", "getRecord", "reinstate"):
        assert required in names
