// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {IERC20} from "./ERC20.sol";

interface IPriceOracle {
    function getPriceE8(address asset) external view returns (uint256);
}

/// @notice Aave-like lending protocol reduced to what the scenario needs (TASKS.md 2.2).
/// Lending side (supply/withdraw) and collateral side (depositCollateral) are separate balances:
/// collateral never adds borrowable liquidity. No interest accrual, no liquidation: rates are display only.
contract MiniLend {
    struct ReserveData {
        address asset;
        uint256 totalSupplied;
        uint256 totalBorrowed;
        uint256 availableLiquidity;
        uint256 utilizationBps;
        uint256 supplyRateBps;
        uint256 borrowRateBps;
        uint256 totalCollateral;
        uint16 ltvBps;
        bool borrowable;
        bool frozen;
        bool paused;
    }

    struct Reserve {
        bool listed;
        bool borrowable;
        bool frozen;
        bool paused;
        uint16 ltvBps;
        uint8 decimals;
        uint256 totalSupplied;
        uint256 totalBorrowed;
        uint256 totalCollateral;
    }

    IPriceOracle public immutable oracle;
    address public protocolGuardian;
    address[] private assets;
    mapping(address => Reserve) private reserves;
    mapping(address => mapping(address => uint256)) private supplied; // user => asset => amount
    mapping(address => mapping(address => uint256)) private collateral;
    mapping(address => mapping(address => uint256)) private borrowed;

    event Supplied(address indexed asset, address indexed from, address indexed onBehalfOf, uint256 amount);
    event Withdrawn(address indexed asset, address indexed user, address to, uint256 amount);
    event CollateralDeposited(address indexed asset, address indexed user, uint256 amount);
    event Borrowed(address indexed asset, address indexed user, uint256 amount);
    event Repaid(address indexed asset, address indexed user, uint256 amount);
    event ReserveListed(address indexed asset, bool borrowable, uint16 ltvBps);
    event ReserveFrozen(address indexed asset, bool frozen);
    event ReservePaused(address indexed asset, bool paused);
    event LtvUpdated(address indexed asset, uint16 ltvBps);
    event GuardianTransferred(address indexed previous, address indexed next);

    modifier onlyGuardian() {
        require(msg.sender == protocolGuardian, "MiniLend: only guardian");
        _;
    }

    constructor(IPriceOracle oracle_, address protocolGuardian_) {
        oracle = oracle_;
        protocolGuardian = protocolGuardian_;
    }

    // ---------- lending side (USDC, WETH) ----------

    function supply(address asset, uint256 amount, address onBehalfOf) external {
        Reserve storage r = _active(asset);
        require(!r.frozen, "MiniLend: frozen");
        require(r.borrowable, "MiniLend: not borrowable");
        require(IERC20(asset).transferFrom(msg.sender, address(this), amount), "MiniLend: transfer failed");
        supplied[onBehalfOf][asset] += amount;
        r.totalSupplied += amount;
        emit Supplied(asset, msg.sender, onBehalfOf, amount);
    }

    /// @param amount type(uint256).max withdraws min(position, available liquidity) and returns 0 if nothing can leave
    function withdraw(address asset, uint256 amount, address to) external returns (uint256 withdrawn) {
        Reserve storage r = _active(asset);
        uint256 position = supplied[msg.sender][asset];
        uint256 liquidity = r.totalSupplied - r.totalBorrowed;
        if (amount == type(uint256).max) {
            withdrawn = position < liquidity ? position : liquidity;
            if (withdrawn == 0) return 0;
        } else {
            require(amount <= position, "MiniLend: insufficient balance");
            require(amount <= liquidity, "MiniLend: insufficient liquidity");
            withdrawn = amount;
        }
        supplied[msg.sender][asset] = position - withdrawn;
        r.totalSupplied -= withdrawn;
        require(IERC20(asset).transfer(to, withdrawn), "MiniLend: transfer failed");
        emit Withdrawn(asset, msg.sender, to, withdrawn);
    }

    // ---------- collateral side and borrowing ----------

    function depositCollateral(address asset, uint256 amount) external {
        Reserve storage r = _active(asset);
        require(!r.frozen, "MiniLend: frozen");
        require(r.ltvBps > 0, "MiniLend: not collateral");
        require(IERC20(asset).transferFrom(msg.sender, address(this), amount), "MiniLend: transfer failed");
        collateral[msg.sender][asset] += amount;
        r.totalCollateral += amount;
        emit CollateralDeposited(asset, msg.sender, amount);
    }

    function borrow(address asset, uint256 amount) external {
        Reserve storage r = _active(asset);
        require(!r.frozen, "MiniLend: frozen");
        require(r.borrowable, "MiniLend: not borrowable");
        require(amount <= r.totalSupplied - r.totalBorrowed, "MiniLend: insufficient liquidity");
        borrowed[msg.sender][asset] += amount;
        r.totalBorrowed += amount;
        require(_debtValueE8(msg.sender) <= _borrowCapacityE8(msg.sender), "MiniLend: insufficient collateral");
        require(IERC20(asset).transfer(msg.sender, amount), "MiniLend: transfer failed");
        emit Borrowed(asset, msg.sender, amount);
    }

    /// @dev capped at the caller's debt
    function repay(address asset, uint256 amount) external {
        Reserve storage r = _active(asset);
        uint256 debt = borrowed[msg.sender][asset];
        uint256 paid = amount < debt ? amount : debt;
        require(IERC20(asset).transferFrom(msg.sender, address(this), paid), "MiniLend: transfer failed");
        borrowed[msg.sender][asset] = debt - paid;
        r.totalBorrowed -= paid;
        emit Repaid(asset, msg.sender, paid);
    }

    // ---------- protocol guardian ----------

    function listReserve(address asset, bool borrowable, uint16 ltvBps) external onlyGuardian {
        Reserve storage r = reserves[asset];
        require(!r.listed, "MiniLend: already listed");
        r.listed = true;
        r.borrowable = borrowable;
        r.ltvBps = ltvBps;
        r.decimals = IERC20(asset).decimals();
        assets.push(asset);
        emit ReserveListed(asset, borrowable, ltvBps);
    }

    function setReserveFrozen(address asset, bool frozen) external onlyGuardian {
        _listed(asset).frozen = frozen;
        emit ReserveFrozen(asset, frozen);
    }

    function setReservePaused(address asset, bool paused) external onlyGuardian {
        _listed(asset).paused = paused;
        emit ReservePaused(asset, paused);
    }

    function setLtv(address asset, uint16 ltvBps) external onlyGuardian {
        _listed(asset).ltvBps = ltvBps;
        emit LtvUpdated(asset, ltvBps);
    }

    /// @notice lets the deployer configure the reserves, then hand the role to the protocol guardian
    function transferGuardian(address next) external onlyGuardian {
        emit GuardianTransferred(protocolGuardian, next);
        protocolGuardian = next;
    }

    // ---------- reads ----------

    function getAssets() external view returns (address[] memory) {
        return assets;
    }

    function getReservesData() external view returns (ReserveData[] memory out) {
        out = new ReserveData[](assets.length);
        for (uint256 i = 0; i < assets.length; i++) {
            Reserve storage r = reserves[assets[i]];
            uint256 utilization = r.totalSupplied == 0 ? 0 : (r.totalBorrowed * 10_000) / r.totalSupplied;
            (uint256 supplyRate, uint256 borrowRate) = r.borrowable ? rates(utilization) : (0, 0);
            out[i] = ReserveData({
                asset: assets[i],
                totalSupplied: r.totalSupplied,
                totalBorrowed: r.totalBorrowed,
                availableLiquidity: r.totalSupplied - r.totalBorrowed,
                utilizationBps: utilization,
                supplyRateBps: supplyRate,
                borrowRateBps: borrowRate,
                totalCollateral: r.totalCollateral,
                ltvBps: r.ltvBps,
                borrowable: r.borrowable,
                frozen: r.frozen,
                paused: r.paused
            });
        }
    }

    function getUserSupplied(address user, address asset) external view returns (uint256) {
        return supplied[user][asset];
    }

    function getUserCollateral(address user, address asset) external view returns (uint256) {
        return collateral[user][asset];
    }

    function getUserBorrowed(address user, address asset) external view returns (uint256) {
        return borrowed[user][asset];
    }

    /// @notice Kinked model (TASKS.md 2.2): borrow = 100 + 300·U/80% up to 80 %, then 400 + 7500·(U−80%)/20%;
    /// supply = borrow · U · 85 %. At U = 100 %: borrow 7900 bps, supply 6715 bps (the bait yield).
    function rates(uint256 utilizationBps) public pure returns (uint256 supplyBps, uint256 borrowBps) {
        borrowBps = utilizationBps <= 8000
            ? 100 + (300 * utilizationBps) / 8000
            : 400 + (7500 * (utilizationBps - 8000)) / 2000;
        supplyBps = (borrowBps * utilizationBps * 85) / 1_000_000;
    }

    // ---------- internals ----------

    function _listed(address asset) private view returns (Reserve storage r) {
        r = reserves[asset];
        require(r.listed, "MiniLend: not listed");
    }

    function _active(address asset) private view returns (Reserve storage r) {
        r = _listed(asset);
        require(!r.paused, "MiniLend: paused");
    }

    function _valueE8(address asset, uint256 amount) private view returns (uint256) {
        return (amount * oracle.getPriceE8(asset)) / (10 ** reserves[asset].decimals);
    }

    function _debtValueE8(address user) private view returns (uint256 total) {
        for (uint256 i = 0; i < assets.length; i++) {
            uint256 amount = borrowed[user][assets[i]];
            if (amount > 0) total += _valueE8(assets[i], amount);
        }
    }

    function _borrowCapacityE8(address user) private view returns (uint256 total) {
        for (uint256 i = 0; i < assets.length; i++) {
            uint256 amount = collateral[user][assets[i]];
            if (amount > 0) total += (_valueE8(assets[i], amount) * reserves[assets[i]].ltvBps) / 10_000;
        }
    }
}
