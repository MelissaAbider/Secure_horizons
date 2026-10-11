// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {MockERC20} from "../src/MockERC20.sol";
import {RsETH} from "../src/RsETH.sol";
import {MockBridge} from "../src/MockBridge.sol";
import {MockOracle} from "../src/MockOracle.sol";
import {MiniLend, IPriceOracle} from "../src/MiniLend.sol";
import {TreasuryVault} from "../src/TreasuryVault.sol";
import {EvidenceRegistry} from "../src/EvidenceRegistry.sol";
import {IERC20} from "../src/ERC20.sol";

/// @notice Proves the scenario story of TASKS.md 1.2 on the contracts, with the starting state of 2.2.
contract ScenarioTest is Test {
    MockERC20 usdc;
    MockERC20 weth;
    RsETH rseth;
    MockBridge bridge;
    MockOracle oracle;
    MiniLend lendEth;
    MiniLend lendAvax;
    TreasuryVault vault;
    EvidenceRegistry registry;

    address owner = makeAddr("owner");
    address guardian = makeAddr("guardian");
    address protocolGuardian = makeAddr("protocolGuardian");
    address lender = makeAddr("lender"); // bots[0]
    address borrower = makeAddr("borrower"); // bots[1]
    address attacker = makeAddr("attacker");

    uint256 constant E18 = 1e18;
    uint256 constant E6 = 1e6;

    function setUp() public {
        usdc = new MockERC20("USD Coin (test)", "USDC", 6);
        weth = new MockERC20("Wrapped Ether (test)", "WETH", 18);
        address predicted = vm.computeCreateAddress(address(this), vm.getNonce(address(this)) + 1);
        rseth = new RsETH(predicted);
        bridge = new MockBridge(IERC20(address(weth)), rseth);
        oracle = new MockOracle();
        lendEth = new MiniLend(IPriceOracle(address(oracle)), address(this));
        lendAvax = new MiniLend(IPriceOracle(address(oracle)), address(this));
        vault = new TreasuryVault(owner, guardian);
        registry = new EvidenceRegistry();
        oracle.setPriceE8(address(usdc), 1e8);
        oracle.setPriceE8(address(weth), 2500e8);
        oracle.setPriceE8(address(rseth), 2500e8);
        _list(lendEth);
        _list(lendAvax);
        _seed();
    }

    function _list(MiniLend m) internal {
        m.listReserve(address(usdc), true, 8000);
        m.listReserve(address(weth), true, 8000);
        m.listReserve(address(rseth), false, 7500);
        m.transferGuardian(protocolGuardian);
    }

    /// starting state of TASKS.md 2.2 (what T2's seed reproduces on chain)
    function _seed() internal {
        // lender supplies the non-vault part of each market
        _supply(lender, lendEth, weth, 1850 * E18);
        _supply(lender, lendEth, usdc, 2_600_000 * E6);
        _supply(lender, lendAvax, weth, 900 * E18);
        _supply(lender, lendAvax, usdc, 1_700_000 * E6);
        // borrower: 1,200 backed rsETH + USDC collateral, then the historical borrows
        weth.mint(borrower, 1200 * E18);
        usdc.mint(borrower, 7_500_000 * E6);
        vm.startPrank(borrower);
        weth.approve(address(bridge), type(uint256).max);
        bridge.deposit(1200 * E18);
        _collateral(lendEth, rseth, 900 * E18);
        _collateral(lendAvax, rseth, 300 * E18);
        _collateral(lendEth, usdc, 4_500_000 * E6);
        _collateral(lendAvax, usdc, 3_000_000 * E6);
        lendEth.borrow(address(weth), 1200 * E18);
        lendEth.borrow(address(usdc), 1_800_000 * E6);
        lendAvax.borrow(address(weth), 550 * E18);
        lendAvax.borrow(address(usdc), 1_100_000 * E6);
        vm.stopPrank();
        // the treasury vault: tokens sent to the vault, then supplied by the owner
        weth.mint(address(vault), 250 * E18);
        usdc.mint(address(vault), 700_000 * E6);
        vm.startPrank(owner);
        vault.supply(address(lendEth), address(weth), 150 * E18);
        vault.supply(address(lendEth), address(usdc), 400_000 * E6);
        vault.supply(address(lendAvax), address(weth), 100 * E18);
        vault.supply(address(lendAvax), address(usdc), 300_000 * E6);
        vm.stopPrank();
    }

    function _supply(address who, MiniLend m, MockERC20 token, uint256 amount) internal {
        token.mint(who, amount);
        vm.startPrank(who);
        token.approve(address(m), amount);
        m.supply(address(token), amount, who);
        vm.stopPrank();
    }

    function _collateral(MiniLend m, IERC20 token, uint256 amount) internal {
        token.approve(address(m), amount);
        m.depositCollateral(address(token), amount);
    }

    function _reserve(MiniLend m, address asset) internal view returns (MiniLend.ReserveData memory r) {
        MiniLend.ReserveData[] memory all = m.getReservesData();
        for (uint256 i = 0; i < all.length; i++) if (all[i].asset == asset) return all[i];
        revert("reserve not found");
    }

    function _forgeAndPostCollateral() internal {
        bridge.forgedRelease(attacker, 5000 * E18);
        vm.startPrank(attacker);
        rseth.approve(address(lendEth), type(uint256).max);
        lendEth.depositCollateral(address(rseth), 5000 * E18);
        vm.stopPrank();
    }

    function _drainWeth() internal returns (uint256 borrows) {
        vm.startPrank(attacker);
        uint256 available = _reserve(lendEth, address(weth)).availableLiquidity;
        while (available > 0) {
            uint256 chunk = available < 100 * E18 ? available : 100 * E18;
            lendEth.borrow(address(weth), chunk);
            borrows++;
            available -= chunk;
        }
        vm.stopPrank();
    }

    // ---------- starting state ----------

    function test_seed_state_matches_2_2() public view {
        MiniLend.ReserveData memory w = _reserve(lendEth, address(weth));
        assertEq(w.totalSupplied, 2000 * E18);
        assertEq(w.totalBorrowed, 1200 * E18);
        assertEq(w.utilizationBps, 6000);
        assertEq(w.supplyRateBps, 165);
        assertEq(w.borrowRateBps, 325);
        MiniLend.ReserveData memory a = _reserve(lendAvax, address(weth));
        assertEq(a.utilizationBps, 5500);
        assertEq(a.supplyRateBps, 143);
        assertEq(a.borrowRateBps, 306);
        assertEq(bridge.backingRatioBps(), 10_000);
        assertEq(lendEth.getUserSupplied(address(vault), address(weth)), 150 * E18);
        assertEq(lendAvax.getUserSupplied(address(vault), address(usdc)), 300_000 * E6);
    }

    function test_borrower_margin_is_195_weth() public {
        vm.prank(borrower);
        lendEth.borrow(address(weth), 195 * E18); // exactly the remaining capacity
        vm.prank(borrower);
        vm.expectRevert("MiniLend: insufficient collateral");
        lendEth.borrow(address(weth), 1e15); // 0.001 WETH more is refused
    }

    // ---------- the attack ----------

    function test_forged_release_drops_backing_to_1935() public {
        assertEq(bridge.conservationGap(), 0);
        assertEq(bridge.sourceNonce(), bridge.destinationNonce());
        bridge.forgedRelease(attacker, 5000 * E18);
        assertEq(rseth.totalSupply(), 6200 * E18);
        assertEq(bridge.backingRatioBps(), 1935);
        assertEq(bridge.conservationGap(), 5000 * E18);
        assertEq(bridge.destinationNonce(), bridge.sourceNonce() + 1);
        assertEq(bridge.totalBacking(), bridge.sourceLocked());
    }

    function test_bridge_pause_stops_both_flows() public {
        vm.prank(attacker);
        vm.expectRevert("Bridge: only owner");
        bridge.pause();
        bridge.pause();
        bridge.pause(); // idempotent
        vm.expectRevert("Bridge: paused");
        bridge.forgedRelease(attacker, 1);
        vm.prank(borrower);
        vm.expectRevert("Bridge: paused");
        bridge.deposit(1);
    }

    function test_drain_without_reaction_leaves_vault_stuck() public {
        _forgeAndPostCollateral();
        assertEq(_drainWeth(), 8);
        MiniLend.ReserveData memory w = _reserve(lendEth, address(weth));
        assertEq(w.availableLiquidity, 0);
        assertEq(w.supplyRateBps, 6715); // the bait yield
        assertEq(w.borrowRateBps, 7900);
        vm.prank(attacker);
        vm.expectRevert("MiniLend: insufficient liquidity");
        lendEth.borrow(address(weth), 1);
        vm.prank(guardian);
        assertEq(vault.emergencyWithdraw(address(lendEth), address(weth)), 0); // passive treasury: nothing leaves
    }

    function test_guardian_exits_before_drain_recovers_everything() public {
        _forgeAndPostCollateral();
        vm.startPrank(guardian);
        vault.pauseDeposits();
        assertEq(vault.emergencyWithdraw(address(lendEth), address(usdc)), 400_000 * E6);
        assertEq(vault.emergencyWithdraw(address(lendEth), address(weth)), 150 * E18);
        assertEq(vault.emergencyWithdraw(address(lendAvax), address(usdc)), 300_000 * E6);
        assertEq(vault.emergencyWithdraw(address(lendAvax), address(weth)), 100 * E18);
        vm.stopPrank();
        _drainWeth();
        assertEq(weth.balanceOf(address(vault)), 250 * E18);
        assertEq(usdc.balanceOf(address(vault)), 700_000 * E6);
        vm.prank(lender); // the passive lender is the one stuck
        assertEq(lendEth.withdraw(address(weth), type(uint256).max, lender), 0);
    }

    // ---------- protocol and vault rules ----------

    function test_frozen_allows_withdraw_blocks_supply_and_borrow() public {
        vm.prank(protocolGuardian);
        lendEth.setReserveFrozen(address(weth), true);
        vm.prank(guardian);
        assertEq(vault.emergencyWithdraw(address(lendEth), address(weth)), 150 * E18);
        weth.mint(lender, 1 * E18);
        vm.startPrank(lender);
        weth.approve(address(lendEth), 1 * E18);
        vm.expectRevert("MiniLend: frozen");
        lendEth.supply(address(weth), 1 * E18, lender);
        vm.stopPrank();
        vm.prank(borrower);
        vm.expectRevert("MiniLend: frozen");
        lendEth.borrow(address(weth), 1);
    }

    function test_paused_blocks_everything_and_emergency_withdraw_reverts() public {
        vm.prank(protocolGuardian);
        lendEth.setReservePaused(address(weth), true);
        vm.prank(guardian);
        vm.expectRevert("MiniLend: paused");
        vault.emergencyWithdraw(address(lendEth), address(weth));
    }

    function test_withdraw_errors() public {
        vm.startPrank(lender);
        vm.expectRevert("MiniLend: insufficient balance");
        lendEth.withdraw(address(weth), 1851 * E18, lender);
        vm.expectRevert("MiniLend: insufficient liquidity");
        lendEth.withdraw(address(weth), 801 * E18, lender);
        vm.stopPrank();
        vm.prank(attacker); // no position: max withdraw returns 0 without revert
        assertEq(lendEth.withdraw(address(weth), type(uint256).max, attacker), 0);
    }

    function test_repay_is_capped_at_debt() public {
        weth.mint(borrower, 10 * E18);
        uint256 before = weth.balanceOf(borrower);
        vm.startPrank(borrower);
        weth.approve(address(lendEth), type(uint256).max);
        lendEth.repay(address(weth), 5000 * E18); // asks for more than the debt
        vm.stopPrank();
        assertEq(lendEth.getUserBorrowed(borrower, address(weth)), 0);
        assertEq(weth.balanceOf(borrower), before - 1200 * E18); // only the 1,200 WETH debt was taken
    }

    function test_vault_roles() public {
        vm.prank(attacker);
        vm.expectRevert("Vault: only guardian or owner");
        vault.emergencyWithdraw(address(lendEth), address(weth));
        vm.prank(guardian);
        vault.pauseDeposits();
        vm.prank(guardian);
        vault.pauseDeposits(); // idempotent
        vm.prank(guardian);
        vm.expectRevert("Vault: only owner");
        vault.unpauseDeposits();
        vm.prank(owner);
        vm.expectRevert("Vault: deposits paused");
        vault.supply(address(lendEth), address(weth), 1);
        vm.prank(owner);
        vault.unpauseDeposits();
        assertFalse(vault.depositsPaused());
    }

    function test_only_protocol_guardian_admin_and_only_bridge_mints() public {
        vm.expectRevert("MiniLend: only guardian");
        lendEth.setReserveFrozen(address(weth), true);
        vm.expectRevert("RsETH: only bridge");
        rseth.mint(attacker, 1);
        vm.prank(attacker);
        vm.expectRevert("Oracle: only owner");
        oracle.setPriceE8(address(weth), 1);
    }

    function test_registry_anchors_once() public {
        bytes32 h = keccak256("decision");
        registry.anchor(h, "decision", "s3://evidence/DEC-1.json");
        assertEq(registry.anchoredAt(h), block.number);
        vm.expectRevert("Evidence: already anchored");
        registry.anchor(h, "decision", "again");
    }
}
