"""Read/write adapter for UAVIdentityRegistry."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from eth_account import Account
from web3 import Web3

from app.auth.blockchain.client import connect
from app.auth.blockchain.compiler import load_artifact
from app.core.clocks import now_ns
from app.core.constants import CHAIN_ID, DEFAULT_RPC_URL, TEST_KEY_WARNING


class RegistryAdapter:
    def __init__(
        self,
        rpc_url: str = DEFAULT_RPC_URL,
        address: str | None = None,
        private_key: str | None = None,
        timeout_s: float = 5.0,
        confirmation_blocks: int = 1,
    ) -> None:
        self.rpc_url = rpc_url
        self.timeout_s = timeout_s
        self.confirmation_blocks = confirmation_blocks
        self.artifact = load_artifact()
        self.w3 = connect(rpc_url, timeout_s=timeout_s)
        self.address = Web3.to_checksum_address(address) if address else None
        self.private_key = private_key
        self._contract = None
        if self.address:
            self._contract = self.w3.eth.contract(address=self.address, abi=self.artifact["abi"])

    @property
    def contract(self):
        if self._contract is None:
            raise RuntimeError("registry contract address is not configured")
        return self._contract

    def get_record(self, uav_id: str) -> dict[str, Any]:
        data = self.contract.functions.getRecord(uav_id).call()
        return {
            "uav_id": data[0],
            "public_key": bytes(data[1]),
            "public_key_hash": "0x" + bytes(data[2]).hex(),
            "role": int(data[3]),
            "status": int(data[4]),
            "registered_at": int(data[5]),
            "updated_at": int(data[6]),
            "registered_block": int(data[7]),
            "updated_block": int(data[8]),
        }

    def _account(self):
        if not self.private_key:
            raise RuntimeError("registrar private key is not configured")
        return Account.from_key(self.private_key)

    def _transact(self, fn) -> dict[str, Any]:
        acct = self._account()
        nonce = self.w3.eth.get_transaction_count(acct.address)
        gas_price = self.w3.eth.gas_price or 1
        tx = fn.build_transaction(
            {
                "from": acct.address,
                "nonce": nonce,
                "chainId": CHAIN_ID,
                "gas": 1_500_000,
                "gasPrice": gas_price,
            }
        )
        signed = acct.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
        t0 = now_ns()
        tx_hash = self.w3.eth.send_raw_transaction(raw)
        submit_ns = now_ns() - t0
        t1 = now_ns()
        receipt = self.w3.eth.wait_for_transaction_receipt(
            tx_hash, timeout=max(30, int(self.timeout_s * 10)), poll_latency=0.2
        )
        if self.confirmation_blocks > 1:
            target = receipt.blockNumber + self.confirmation_blocks - 1
            while self.w3.eth.block_number < target:
                time.sleep(0.2)
        confirm_ns = now_ns() - t1
        return {
            "tx_hash": tx_hash.hex() if hasattr(tx_hash, "hex") else Web3.to_hex(tx_hash),
            "block_number": receipt.blockNumber,
            "gas_used": receipt.gasUsed,
            "status": receipt.status,
            "submit_ns": submit_ns,
            "confirm_ns": confirm_ns,
            "warning": TEST_KEY_WARNING,
        }

    def register(self, uav_id: str, public_key: bytes, role: int) -> dict[str, Any]:
        return self._transact(self.contract.functions.register(uav_id, public_key, int(role)))

    def revoke(self, uav_id: str) -> dict[str, Any]:
        return self._transact(self.contract.functions.revoke(uav_id))

    def suspend(self, uav_id: str) -> dict[str, Any]:
        return self._transact(self.contract.functions.suspend(uav_id))

    def reinstate(self, uav_id: str) -> dict[str, Any]:
        return self._transact(self.contract.functions.reinstate(uav_id))

    def update_role(self, uav_id: str, role: int) -> dict[str, Any]:
        return self._transact(self.contract.functions.updateRole(uav_id, int(role)))

    def update_key(self, uav_id: str, public_key: bytes) -> dict[str, Any]:
        return self._transact(self.contract.functions.updateKey(uav_id, public_key))

    def record_audit(self, uav_id: str, outcome_hash: bytes) -> dict[str, Any]:
        if len(outcome_hash) != 32:
            raise ValueError("outcome hash must be 32 bytes")
        return self._transact(self.contract.functions.recordAuthAudit(uav_id, outcome_hash))

    def transfer_admin(self, new_admin: str) -> dict[str, Any]:
        return self._transact(self.contract.functions.transferAdmin(new_admin))

    def deploy(self) -> dict[str, Any]:
        acct = self._account()
        contract = self.w3.eth.contract(
            abi=self.artifact["abi"], bytecode=self.artifact["bytecode"]
        )
        nonce = self.w3.eth.get_transaction_count(acct.address)
        gas_price = self.w3.eth.gas_price or 1
        tx = contract.constructor().build_transaction(
            {
                "from": acct.address,
                "nonce": nonce,
                "chainId": CHAIN_ID,
                "gas": 3_000_000,
                "gasPrice": gas_price,
            }
        )
        signed = acct.sign_transaction(tx)
        raw = getattr(signed, "raw_transaction", None) or signed.rawTransaction
        tx_hash = self.w3.eth.send_raw_transaction(raw)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        self.address = receipt.contractAddress
        self._contract = self.w3.eth.contract(address=self.address, abi=self.artifact["abi"])
        return {
            "address": self.address,
            "tx_hash": tx_hash.hex() if hasattr(tx_hash, "hex") else Web3.to_hex(tx_hash),
            "block_number": receipt.blockNumber,
            "gas_used": receipt.gasUsed,
            "chain_id": CHAIN_ID,
            "bytecode_sha256": self.artifact.get("bytecodeSha256"),
            "source_sha256": self.artifact.get("sourceSha256"),
            "solc_version": self.artifact.get("solcVersion"),
            "registrar": acct.address,
        }


def save_deployment(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
