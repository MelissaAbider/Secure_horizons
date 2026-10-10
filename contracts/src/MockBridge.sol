// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IERC20} from "./ERC20.sol";
import {RsETH} from "./RsETH.sol";

/// @notice Issuer of rsETH. deposit() locks WETH and mints the same amount of rsETH (backed).
/// forgedRelease() is the deliberate flaw of the scenario: it mints rsETH with no WETH behind it,
/// like the forged release of the April 2026 incident. Anyone can call it.
contract MockBridge {
    IERC20 public immutable weth;
    RsETH public immutable rseth;
    uint256 public totalBacking; // WETH actually locked

    event Deposited(address indexed user, uint256 amount);
    event Released(address indexed to, uint256 amount, bool backed);

    constructor(IERC20 weth_, RsETH rseth_) {
        weth = weth_;
        rseth = rseth_;
    }

    function deposit(uint256 wethAmount) external {
        require(weth.transferFrom(msg.sender, address(this), wethAmount), "Bridge: transfer failed");
        totalBacking += wethAmount;
        rseth.mint(msg.sender, wethAmount);
        emit Deposited(msg.sender, wethAmount);
        emit Released(msg.sender, wethAmount, true);
    }

    function forgedRelease(address to, uint256 amount) external {
        rseth.mint(to, amount);
        emit Released(to, amount, false);
    }

    /// @return backing in basis points: totalBacking * 10000 / rsETH supply (10000 when the supply is 0)
    function backingRatioBps() external view returns (uint256) {
        uint256 supply = rseth.totalSupply();
        return supply == 0 ? 10_000 : (totalBacking * 10_000) / supply;
    }
}
