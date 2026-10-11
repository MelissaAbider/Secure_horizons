// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @dev The one Safe function the module needs (Safe v1.4.1 ModuleManager). operation 0 = CALL.
interface ISafe {
    function execTransactionFromModuleReturnData(address to, uint256 value, bytes calldata data, uint8 operation)
        external
        returns (bool success, bytes memory returnData);
}

/// @notice The teller window (T10): a Safe module that executes only the operations sealed in a Merkle root.
/// root = the seal. Only the Safe sets it, i.e. a Safe transaction signed by the owners' threshold (the front door).
/// operator = the platform's teller-window key. It submits sealed operations and can do nothing else.
/// A leaf is one allowed operation: target contract, function selector, number of 32-byte argument words, and
/// the value of the pinned words (bit i of pinMask pins word i). Unpinned words, such as amounts, stay free.
/// Leaves are double hashed and pairs are sorted, as in OpenZeppelin MerkleProof, so the list can be rebuilt
/// and checked by anyone (sealed/tree.py).
contract SealedListModule {
    ISafe public immutable safe;
    address public operator;
    bytes32 public root;

    event RootSealed(bytes32 indexed previousRoot, bytes32 indexed root);
    event OperatorSet(address indexed operator);
    event Executed(bytes32 indexed leaf, address indexed target, bytes4 indexed selector);

    error OnlySafe();
    error OnlyOperator();
    error ForbiddenTarget(address target);
    error BadCalldata();
    error NotInSealedList(bytes32 leaf, bytes32 computedRoot, bytes32 sealedRoot);
    error CallFailed(bytes returnData);

    modifier onlySafe() {
        if (msg.sender != address(safe)) revert OnlySafe();
        _;
    }

    constructor(address safe_, address operator_) {
        safe = ISafe(safe_);
        operator = operator_;
        emit OperatorSet(operator_);
    }

    /// @notice seals a new list. bytes32(0) revokes everything.
    function setRoot(bytes32 root_) external onlySafe {
        emit RootSealed(root, root_);
        root = root_;
    }

    function setOperator(address operator_) external onlySafe {
        operator = operator_;
        emit OperatorSet(operator_);
    }

    /// @notice runs one sealed operation from the Safe: CALL only (never delegatecall), no native value,
    /// never on the Safe itself (owners, threshold, modules) nor on this module (root, operator).
    function execute(address target, bytes calldata data, uint256 pinMask, bytes32[] calldata proof)
        external
        returns (bytes memory)
    {
        if (msg.sender != operator) revert OnlyOperator();
        if (target == address(safe) || target == address(this)) revert ForbiddenTarget(target);
        bytes32 leaf = leafOf(target, data, pinMask);
        bytes32 computed = processProof(proof, leaf);
        if (computed != root) revert NotInSealedList(leaf, computed, root);
        (bool ok, bytes memory ret) = safe.execTransactionFromModuleReturnData(target, 0, data, 0);
        if (!ok) revert CallFailed(ret);
        emit Executed(leaf, target, bytes4(data[:4]));
        return ret;
    }

    /// @notice the leaf an operation proves against: amounts can change, pinned words cannot
    function leafOf(address target, bytes calldata data, uint256 pinMask) public pure returns (bytes32) {
        if (data.length < 4 || (data.length - 4) % 32 != 0) revert BadCalldata();
        uint256 words = (data.length - 4) / 32;
        if (pinMask >> words != 0) revert BadCalldata();
        bytes memory pinned;
        for (uint256 i; i < words; ++i) {
            if (pinMask & (1 << i) != 0) pinned = bytes.concat(pinned, data[4 + 32 * i:36 + 32 * i]);
        }
        return
            keccak256(bytes.concat(keccak256(abi.encode(target, bytes4(data[:4]), words, pinMask, keccak256(pinned)))));
    }

    function processProof(bytes32[] calldata proof, bytes32 leaf) public pure returns (bytes32 node) {
        node = leaf;
        for (uint256 i; i < proof.length; ++i) {
            bytes32 sibling = proof[i];
            node = node < sibling ? keccak256(abi.encode(node, sibling)) : keccak256(abi.encode(sibling, node));
        }
    }
}
