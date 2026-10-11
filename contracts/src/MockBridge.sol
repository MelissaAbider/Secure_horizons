// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IERC20} from "./ERC20.sol";
import {RsETH} from "./RsETH.sol";

/// @notice Simulated cross-chain route of rsETH (LayerZero/OFT style), both ends in one contract.
/// deposit() is the healthy flow: WETH is locked on the "source" side, both nonces advance, the same amount of rsETH
/// is released on the "destination" side. forgedRelease() is the deliberate flaw of the scenario: a release with no
/// source lock and no source message, like the forged release of the April 2026 incident. Anyone can call it.
/// Invariants the monitor checks: destinationReleased <= sourceLocked and destinationNonce <= sourceNonce.
contract MockBridge {
    IERC20 public immutable weth;
    RsETH public immutable rseth;
    address public immutable owner;
    uint256 public sourceLocked; // WETH locked on the source side
    uint256 public destinationReleased; // rsETH released on the destination side
    uint64 public sourceNonce;
    uint64 public destinationNonce;
    bool public paused;

    event Deposited(address indexed user, uint256 amount, uint64 sourceNonce);
    event Released(address indexed to, uint256 amount, uint64 destinationNonce, bool sourceVerified);
    event Paused(address indexed by);

    constructor(IERC20 weth_, RsETH rseth_) {
        weth = weth_;
        rseth = rseth_;
        owner = msg.sender;
    }

    function deposit(uint256 wethAmount) external {
        require(!paused, "Bridge: paused");
        require(weth.transferFrom(msg.sender, address(this), wethAmount), "Bridge: transfer failed");
        sourceLocked += wethAmount;
        sourceNonce += 1;
        emit Deposited(msg.sender, wethAmount, sourceNonce);
        destinationNonce += 1;
        destinationReleased += wethAmount;
        rseth.mint(msg.sender, wethAmount);
        emit Released(msg.sender, wethAmount, destinationNonce, true);
    }

    function forgedRelease(address to, uint256 amount) external {
        require(!paused, "Bridge: paused");
        destinationNonce += 1;
        destinationReleased += amount;
        rseth.mint(to, amount);
        emit Released(to, amount, destinationNonce, false);
    }

    /// @notice containment switch of the bridge operator (stops both deposits and releases)
    function pause() external {
        require(msg.sender == owner, "Bridge: only owner");
        if (!paused) {
            paused = true;
            emit Paused(msg.sender);
        }
    }

    /// @return rsETH released without a matching source lock
    function conservationGap() external view returns (uint256) {
        return destinationReleased > sourceLocked ? destinationReleased - sourceLocked : 0;
    }

    /// @notice kept for display and older readers: same value as sourceLocked
    function totalBacking() external view returns (uint256) {
        return sourceLocked;
    }

    /// @return backing in basis points: sourceLocked * 10000 / rsETH supply (10000 when the supply is 0)
    function backingRatioBps() external view returns (uint256) {
        uint256 supply = rseth.totalSupply();
        return supply == 0 ? 10_000 : (sourceLocked * 10_000) / supply;
    }
}
