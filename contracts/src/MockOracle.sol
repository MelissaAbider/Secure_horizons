// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @notice USD prices with 8 decimals (Chainlink style). It keeps pricing rsETH at 2,500 USD even when
/// rsETH is unbacked: that blind spot is what lets the attacker borrow against it.
contract MockOracle {
    address public immutable owner;
    mapping(address => uint256) private prices;

    event PriceUpdated(address indexed asset, uint256 priceE8);

    constructor() {
        owner = msg.sender;
    }

    function setPriceE8(address asset, uint256 priceE8) external {
        require(msg.sender == owner, "Oracle: only owner");
        prices[asset] = priceE8;
        emit PriceUpdated(asset, priceE8);
    }

    function getPriceE8(address asset) external view returns (uint256) {
        uint256 price = prices[asset];
        require(price != 0, "Oracle: no price");
        return price;
    }
}
