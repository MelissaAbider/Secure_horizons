// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IERC20} from "./ERC20.sol";

interface ILendingMarket {
    function supply(address asset, uint256 amount, address onBehalfOf) external;
    function withdraw(address asset, uint256 amount, address to) external returns (uint256);
}

/// @notice The client's treasury (a simplified Safe for the MVP).
/// owner = the Safe signers: supplies, withdraws, reopens deposits.
/// guardian = our platform: can only tighten, i.e. pause new deposits and pull funds back INTO this vault.
contract TreasuryVault {
    address public immutable owner;
    address public guardian;
    bool public depositsPaused;

    event DepositsPaused(address indexed by);
    event DepositsUnpaused(address indexed by);
    event EmergencyWithdrawal(address indexed market, address indexed asset, uint256 amount, address indexed by);
    event Supplied(address indexed market, address indexed asset, uint256 amount);
    event Withdrawn(address indexed market, address indexed asset, uint256 amount);
    event GuardianSet(address indexed guardian);

    modifier onlyOwner() {
        require(msg.sender == owner, "Vault: only owner");
        _;
    }

    modifier onlyGuardianOrOwner() {
        require(msg.sender == guardian || msg.sender == owner, "Vault: only guardian or owner");
        _;
    }

    constructor(address owner_, address guardian_) {
        owner = owner_;
        guardian = guardian_;
    }

    /// @dev supplies from the vault's own balance (send the tokens to the vault first)
    function supply(address market, address asset, uint256 amount) external onlyOwner {
        require(!depositsPaused, "Vault: deposits paused");
        require(IERC20(asset).approve(market, amount), "Vault: approve failed");
        ILendingMarket(market).supply(asset, amount, address(this));
        emit Supplied(market, asset, amount);
    }

    function withdraw(address market, address asset, uint256 amount) external onlyOwner {
        uint256 out = ILendingMarket(market).withdraw(asset, amount, address(this));
        emit Withdrawn(market, asset, out);
    }

    /// @notice pulls back whatever can still leave (min of the position and the market liquidity), always to this vault
    function emergencyWithdraw(address market, address asset) external onlyGuardianOrOwner returns (uint256 withdrawn) {
        withdrawn = ILendingMarket(market).withdraw(asset, type(uint256).max, address(this));
        emit EmergencyWithdrawal(market, asset, withdrawn, msg.sender);
    }

    /// @dev idempotent: no revert when already paused
    function pauseDeposits() external onlyGuardianOrOwner {
        if (!depositsPaused) {
            depositsPaused = true;
            emit DepositsPaused(msg.sender);
        }
    }

    function unpauseDeposits() external onlyOwner {
        depositsPaused = false;
        emit DepositsUnpaused(msg.sender);
    }

    function setGuardian(address guardian_) external onlyOwner {
        guardian = guardian_;
        emit GuardianSet(guardian_);
    }
}
