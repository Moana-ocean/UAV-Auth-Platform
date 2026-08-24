"""Shared constants for the UAV-to-GCS authentication experiment."""

from __future__ import annotations

DOMAIN_LABEL = "UAV-GCS-AUTH"
PROTOCOL_VERSION = "1"
DEFAULT_GCS_ID = "GCS-01"
CHAIN_ID = 20245
DEFAULT_RPC_URL = "http://127.0.0.1:8545"
BESU_IMAGE = "hyperledger/besu:26.7.1"
SOLC_VERSION = "0.8.24"
SIGNATURE_ALGORITHM = "ECDSA_P256_SHA256"
HASH_FUNCTION = "SHA-256"
CURVE_NAME = "NIST P-256"
NONCE_BYTES = 16
LARGE_RUN_THRESHOLD = 1000
MAX_REPETITIONS = 10_000
TEST_KEY_WARNING = "NON-PRODUCTION test credential generated for the local experiment."

REASON_CODES = (
    "ACCEPTED",
    "UNKNOWN_IDENTITY",
    "REVOKED_IDENTITY",
    "SUSPENDED_IDENTITY",
    "EXPIRED_CHALLENGE",
    "REPLAY_DETECTED",
    "INVALID_SIGNATURE",
    "UNAUTHORISED_OPERATION",
    "CERTIFICATE_EXPIRED",
    "UNTRUSTED_ISSUER",
    "IDENTITY_SERVICE_UNAVAILABLE",
    "MALFORMED_REQUEST",
    "INTERNAL_ERROR",
)

MECHANISMS = ("x509", "blockchain")

SCENARIOS = (
    "valid_active",
    "unknown_uav",
    "impersonation_wrong_key",
    "replay",
    "modified_nonce",
    "modified_uav_id",
    "modified_operation",
    "expired_challenge",
    "revoked_uav",
    "unauthorised_operation",
    "malformed",
    "expired_certificate",
    "untrusted_issuer",
    "rpc_unavailable",
    "concurrent_valid",
    "concurrent_mixed",
)

X509_ONLY_SCENARIOS = frozenset({"expired_certificate", "untrusted_issuer"})
BLOCKCHAIN_ONLY_SCENARIOS = frozenset({"rpc_unavailable"})
ADVERSARIAL_SCENARIOS = frozenset(SCENARIOS) - {"valid_active", "concurrent_valid"}

ROLE_DELIVERY = 1
ROLE_TELEMETRY = 2
ROLE_OBSERVER = 3
ROLE_NAMES = {ROLE_DELIVERY: "delivery", ROLE_TELEMETRY: "telemetry", ROLE_OBSERVER: "observer"}

OPERATION_TELEMETRY_SUBMIT = "telemetry.submit"
OPERATION_MISSION_RETRIEVE = "mission.retrieve"
OPERATION_DELIVERY_STATUS = "delivery.status"
OPERATION_ADMIN_RECONFIGURE = "admin.reconfigure"

ALLOWED_OPERATIONS = {
    ROLE_DELIVERY: frozenset(
        {OPERATION_TELEMETRY_SUBMIT, OPERATION_MISSION_RETRIEVE, OPERATION_DELIVERY_STATUS}
    ),
    ROLE_TELEMETRY: frozenset({OPERATION_TELEMETRY_SUBMIT}),
    ROLE_OBSERVER: frozenset({OPERATION_DELIVERY_STATUS}),
}

STATUS_NONE = 0
STATUS_ACTIVE = 1
STATUS_SUSPENDED = 2
STATUS_REVOKED = 3
STATUS_NAMES = {
    STATUS_NONE: "none",
    STATUS_ACTIVE: "active",
    STATUS_SUSPENDED: "suspended",
    STATUS_REVOKED: "revoked",
}
