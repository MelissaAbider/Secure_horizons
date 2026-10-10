// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Script} from "forge-std/Script.sol";
import {MockERC20} from "../src/MockERC20.sol";
import {RsETH} from "../src/RsETH.sol";
import {MockBridge} from "../src/MockBridge.sol";
import {MockOracle} from "../src/MockOracle.sol";
import {MiniLend, IPriceOracle} from "../src/MiniLend.sol";
import {TreasuryVault} from "../src/TreasuryVault.sol";
import {EvidenceRegistry} from "../src/EvidenceRegistry.sol";
import {IERC20} from "../src/ERC20.sol";

/// @notice Deploys the scenario world (TASKS.md 2.2). Called by contracts/script/deploy.py, which passes:
/// T1_DEPLOYER_PK, T1_OWNER, T1_GUARDIAN, T1_PROTOCOL_GUARDIAN, T1_OUT (raw JSON written here, then reformatted).
/// Deployment order is fixed so a fresh anvil gives the addresses used in fixtures/.
contract Deploy is Script {
    MockERC20 usdc;
    MockERC20 weth;
    RsETH rseth;
    MockBridge bridge;
    MockOracle oracle;
    MiniLend lendEth;
    MiniLend lendAvax;
    TreasuryVault vault;
    EvidenceRegistry registry;

    function run() external {
        uint256 pk = vm.envUint("T1_DEPLOYER_PK");
        uint256 startBlock = block.number;
        vm.startBroadcast(pk);
        _deploy(vm.addr(pk));
        _configure(vm.envAddress("T1_PROTOCOL_GUARDIAN"));
        vm.stopBroadcast();
        _write(startBlock);
    }

    function _deploy(address deployer) internal {
        usdc = new MockERC20("USD Coin (test)", "USDC", 6);
        weth = new MockERC20("Wrapped Ether (test)", "WETH", 18);
        address predictedBridge = vm.computeCreateAddress(deployer, vm.getNonce(deployer) + 1);
        rseth = new RsETH(predictedBridge);
        bridge = new MockBridge(IERC20(address(weth)), rseth);
        require(address(bridge) == predictedBridge, "Deploy: bridge address mismatch");
        oracle = new MockOracle();
        lendEth = new MiniLend(IPriceOracle(address(oracle)), deployer);
        lendAvax = new MiniLend(IPriceOracle(address(oracle)), deployer);
        vault = new TreasuryVault(vm.envAddress("T1_OWNER"), vm.envAddress("T1_GUARDIAN"));
        registry = new EvidenceRegistry();
    }

    function _configure(address protocolGuardian) internal {
        oracle.setPriceE8(address(usdc), 1e8);
        oracle.setPriceE8(address(weth), 2500e8);
        oracle.setPriceE8(address(rseth), 2500e8);
        _list(lendEth, protocolGuardian);
        _list(lendAvax, protocolGuardian);
    }

    function _list(MiniLend market, address protocolGuardian) internal {
        market.listReserve(address(usdc), true, 8000);
        market.listReserve(address(weth), true, 8000);
        market.listReserve(address(rseth), false, 7500);
        market.transferGuardian(protocolGuardian);
    }

    function _write(uint256 startBlock) internal {
        string memory o = "deployment";
        vm.serializeUint(o, "deployed_at_block", startBlock);
        vm.serializeAddress(o, "USDC", address(usdc));
        vm.serializeAddress(o, "WETH", address(weth));
        vm.serializeAddress(o, "rsETH", address(rseth));
        vm.serializeAddress(o, "MockBridge", address(bridge));
        vm.serializeAddress(o, "MockOracle", address(oracle));
        vm.serializeAddress(o, "lend-eth", address(lendEth));
        vm.serializeAddress(o, "lend-avax", address(lendAvax));
        vm.serializeAddress(o, "TreasuryVault", address(vault));
        string memory json = vm.serializeAddress(o, "EvidenceRegistry", address(registry));
        vm.writeJson(json, vm.envString("T1_OUT"));
    }
}
