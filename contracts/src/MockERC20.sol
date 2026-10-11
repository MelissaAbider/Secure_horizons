// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {ERC20} from "./ERC20.sol";

/// @notice Test token (USDC with 6 decimals, WETH with 18). Only the deployer can mint.
contract MockERC20 is ERC20 {
    address public immutable owner;

    constructor(string memory name_, string memory symbol_, uint8 decimals_) ERC20(name_, symbol_, decimals_) {
        owner = msg.sender;
    }

    function mint(address to, uint256 amount) external {
        require(msg.sender == owner, "MockERC20: only owner");
        _mint(to, amount);
    }
}
