// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @notice Public notebook of decision hashes. An auditor recomputes the hash of a decision record and checks
/// that it was anchored here, at which block. No access control in the MVP (the evidence key anchors by convention).
contract EvidenceRegistry {
    mapping(bytes32 => uint256) public anchoredAt; // hash => block number, 0 if never anchored

    event Anchored(bytes32 indexed recordHash, string kind, string uri, address indexed by);

    /// @param kind "decision", "rules" or "incident"
    function anchor(bytes32 recordHash, string calldata kind, string calldata uri) external {
        require(anchoredAt[recordHash] == 0, "Evidence: already anchored");
        anchoredAt[recordHash] = block.number;
        emit Anchored(recordHash, kind, uri, msg.sender);
    }
}
