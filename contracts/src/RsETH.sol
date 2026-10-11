// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {ERC20} from "./ERC20.sol";

/// @notice Bridged staking token. Only the bridge mints and burns.
contract RsETH is ERC20 {
    address public immutable bridge;

    constructor(address bridge_) ERC20("Restaked ETH (test)", "rsETH", 18) {
        bridge = bridge_;
    }

    function mint(address to, uint256 amount) external {
        require(msg.sender == bridge, "RsETH: only bridge");
        _mint(to, amount);
    }

    function burn(address from, uint256 amount) external {
        require(msg.sender == bridge, "RsETH: only bridge");
        _burn(from, amount);
    }
}
