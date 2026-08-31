// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title UAVIdentityRegistry
/// @notice Permissioned registry of pseudonymous UAV identities for a local
///         research network. Stores no customer, location or private-key data.
/// @dev Checks-effects-interactions: no external calls after state updates.
contract UAVIdentityRegistry {
    uint8 internal constant ROLE_MAX = 3;
    uint16 internal constant MAX_PUBLIC_KEY_BYTES = 128;

    enum Status {
        None,
        Active,
        Suspended,
        Revoked
    }

    struct Record {
        string uavId;
        bytes publicKey;
        bytes32 publicKeyHash;
        uint8 role;
        Status status;
        uint64 registeredAt;
        uint64 updatedAt;
        uint64 registeredBlock;
        uint64 updatedBlock;
    }

    address public admin;
    mapping(address => bool) public registrars;
    mapping(bytes32 => Record) private records;

    event AdminTransferred(address indexed previousAdmin, address indexed newAdmin);
    event RegistrarUpdated(address indexed registrar, bool allowed);
    event Registered(bytes32 indexed idHash, string uavId, bytes32 publicKeyHash, uint8 role, uint64 timestamp);
    event KeyUpdated(bytes32 indexed idHash, string uavId, bytes32 publicKeyHash, uint64 timestamp);
    event RoleUpdated(bytes32 indexed idHash, string uavId, uint8 role, uint64 timestamp);
    event StatusUpdated(bytes32 indexed idHash, string uavId, Status status, uint64 timestamp);
    event Revoked(bytes32 indexed idHash, string uavId, uint64 timestamp);
    event AuthAudited(bytes32 indexed idHash, string uavId, bytes32 outcomeHash, uint64 timestamp);

    error NotAdmin();
    error NotRegistrar();
    error InvalidInput();
    error DuplicateRegistration();
    error UnknownIdentity();
    error AlreadyRevoked();

    modifier onlyAdmin() {
        if (msg.sender != admin) revert NotAdmin();
        _;
    }

    modifier onlyRegistrar() {
        if (!registrars[msg.sender] && msg.sender != admin) revert NotRegistrar();
        _;
    }

    constructor() {
        admin = msg.sender;
        registrars[msg.sender] = true;
        emit AdminTransferred(address(0), msg.sender);
        emit RegistrarUpdated(msg.sender, true);
    }

    function transferAdmin(address newAdmin) external onlyAdmin {
        if (newAdmin == address(0)) revert InvalidInput();
        address previous = admin;
        admin = newAdmin;
        registrars[newAdmin] = true;
        emit AdminTransferred(previous, newAdmin);
        emit RegistrarUpdated(newAdmin, true);
    }

    function setRegistrar(address registrar, bool allowed) external onlyAdmin {
        if (registrar == address(0)) revert InvalidInput();
        registrars[registrar] = allowed;
        emit RegistrarUpdated(registrar, allowed);
    }

    function register(
        string calldata uavId,
        bytes calldata publicKey,
        uint8 role
    ) external onlyRegistrar {
        if (bytes(uavId).length == 0 || publicKey.length == 0) revert InvalidInput();
        _validateRole(role);
        _validatePublicKey(publicKey);
        bytes32 idHash = _id(uavId);
        Record storage rec = records[idHash];
        if (rec.status == Status.Active || rec.status == Status.Suspended) {
            revert DuplicateRegistration();
        }
        if (rec.status == Status.Revoked) {
            revert AlreadyRevoked();
        }
        bytes32 pkHash = sha256(publicKey);
        rec.uavId = uavId;
        rec.publicKey = publicKey;
        rec.publicKeyHash = pkHash;
        rec.role = role;
        rec.status = Status.Active;
        rec.registeredAt = uint64(block.timestamp);
        rec.updatedAt = uint64(block.timestamp);
        rec.registeredBlock = uint64(block.number);
        rec.updatedBlock = uint64(block.number);
        emit Registered(idHash, uavId, pkHash, role, uint64(block.timestamp));
    }

    function updateKey(string calldata uavId, bytes calldata publicKey) external onlyRegistrar {
        _validatePublicKey(publicKey);
        Record storage rec = _requireMutable(uavId);
        rec.publicKey = publicKey;
        rec.publicKeyHash = sha256(publicKey);
        rec.updatedAt = uint64(block.timestamp);
        rec.updatedBlock = uint64(block.number);
        emit KeyUpdated(_id(uavId), uavId, rec.publicKeyHash, uint64(block.timestamp));
    }

    function updateRole(string calldata uavId, uint8 role) external onlyRegistrar {
        _validateRole(role);
        Record storage rec = _requireMutable(uavId);
        rec.role = role;
        rec.updatedAt = uint64(block.timestamp);
        rec.updatedBlock = uint64(block.number);
        emit RoleUpdated(_id(uavId), uavId, role, uint64(block.timestamp));
    }

    function suspend(string calldata uavId) external onlyRegistrar {
        Record storage rec = _requireMutable(uavId);
        rec.status = Status.Suspended;
        rec.updatedAt = uint64(block.timestamp);
        rec.updatedBlock = uint64(block.number);
        emit StatusUpdated(_id(uavId), uavId, Status.Suspended, uint64(block.timestamp));
    }

    function reinstate(string calldata uavId) external onlyRegistrar {
        bytes32 idHash = _id(uavId);
        Record storage rec = records[idHash];
        if (rec.status == Status.None) revert UnknownIdentity();
        if (rec.status == Status.Revoked) revert AlreadyRevoked();
        if (rec.status == Status.Active) revert DuplicateRegistration();
        rec.status = Status.Active;
        rec.updatedAt = uint64(block.timestamp);
        rec.updatedBlock = uint64(block.number);
        emit StatusUpdated(idHash, uavId, Status.Active, uint64(block.timestamp));
    }

    function revoke(string calldata uavId) external onlyRegistrar {
        Record storage rec = _requireKnown(uavId);
        if (rec.status == Status.Revoked) revert AlreadyRevoked();
        rec.status = Status.Revoked;
        rec.updatedAt = uint64(block.timestamp);
        rec.updatedBlock = uint64(block.number);
        emit Revoked(_id(uavId), uavId, uint64(block.timestamp));
        emit StatusUpdated(_id(uavId), uavId, Status.Revoked, uint64(block.timestamp));
    }

    /// @notice Optional audit record. Does not affect authentication decisions.
    function recordAuthAudit(string calldata uavId, bytes32 outcomeHash) external onlyRegistrar {
        _requireKnown(uavId);
        emit AuthAudited(_id(uavId), uavId, outcomeHash, uint64(block.timestamp));
    }

    function getRecord(string calldata uavId)
        external
        view
        returns (
            string memory id,
            bytes memory publicKey,
            bytes32 publicKeyHash,
            uint8 role,
            uint8 status,
            uint64 registeredAt,
            uint64 updatedAt,
            uint64 registeredBlock,
            uint64 updatedBlock
        )
    {
        Record storage rec = records[_id(uavId)];
        return (
            rec.uavId,
            rec.publicKey,
            rec.publicKeyHash,
            rec.role,
            uint8(rec.status),
            rec.registeredAt,
            rec.updatedAt,
            rec.registeredBlock,
            rec.updatedBlock
        );
    }

    function _validateRole(uint8 role) internal pure {
        if (role == 0 || role > ROLE_MAX) revert InvalidInput();
    }

    function _validatePublicKey(bytes calldata publicKey) internal pure {
        if (publicKey.length == 0 || publicKey.length > MAX_PUBLIC_KEY_BYTES) revert InvalidInput();
    }

    function _id(string calldata uavId) internal pure returns (bytes32) {
        return keccak256(bytes(uavId));
    }

    function _requireKnown(string calldata uavId) internal view returns (Record storage rec) {
        rec = records[_id(uavId)];
        if (rec.status == Status.None) revert UnknownIdentity();
    }

    function _requireMutable(string calldata uavId) internal view returns (Record storage rec) {
        rec = _requireKnown(uavId);
        if (rec.status == Status.Revoked) revert AlreadyRevoked();
    }
}
