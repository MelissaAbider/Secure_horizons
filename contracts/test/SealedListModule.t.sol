// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Test} from "forge-std/Test.sol";
import {Safe} from "safe-smart-account/contracts/Safe.sol";
import {SafeL2} from "safe-smart-account/contracts/SafeL2.sol";
import {SafeProxyFactory} from "safe-smart-account/contracts/proxies/SafeProxyFactory.sol";
import {Enum} from "safe-smart-account/contracts/common/Enum.sol";
import {MockERC20} from "../src/MockERC20.sol";
import {MockOracle} from "../src/MockOracle.sol";
import {MiniLend, IPriceOracle} from "../src/MiniLend.sol";
import {IERC20} from "../src/ERC20.sol";
import {SealedListModule} from "../src/SealedListModule.sol";

/// @notice T10: a real Safe 1.4.1 owned by the asset manager alone (one signature) with the teller-window module.
/// The manager seals a list for lend-avax USDC (approve, deposit, withdraw back to the Safe). The operator can run
/// those and nothing else.
contract SealedListModuleTest is Test {
    uint256 constant PIN_FIRST = 1; // approve(spender, *)
    uint256 constant PIN_ASSET_AND_RECIPIENT = 5; // supply(asset, *, onBehalfOf) / withdraw(asset, *, to)
    uint256 constant E6 = 1e6;

    MockERC20 usdc;
    MiniLend lendAvax;
    MiniLend lendEth;
    Safe safe;
    SealedListModule module;

    address manager; // the asset manager: the Safe's only owner, threshold 1
    uint256 managerKey;
    address operator = makeAddr("operator");
    address stranger = makeAddr("stranger");

    function setUp() public {
        usdc = new MockERC20("USD Coin (test)", "USDC", 6);
        MockOracle oracle = new MockOracle();
        lendAvax = new MiniLend(IPriceOracle(address(oracle)), address(this));
        lendEth = new MiniLend(IPriceOracle(address(oracle)), address(this));
        lendAvax.listReserve(address(usdc), true, 8000);
        lendEth.listReserve(address(usdc), true, 8000);

        (manager, managerKey) = makeAddrAndKey("assetManager");
        address[] memory owners = new address[](1);
        owners[0] = manager;
        SafeProxyFactory factory = new SafeProxyFactory();
        bytes memory setup =
            abi.encodeCall(Safe.setup, (owners, 1, address(0), "", address(0), address(0), 0, payable(address(0))));
        safe = Safe(payable(address(factory.createProxyWithNonce(address(new SafeL2()), setup, 1))));
        module = new SealedListModule(address(safe), operator);
        assertTrue(_safeTx(address(safe), abi.encodeWithSignature("enableModule(address)", address(module))));
        usdc.mint(address(safe), 1_000_000 * E6);

        assertTrue(_safeTx(address(module), abi.encodeCall(SealedListModule.setRoot, (_root(_list(lendAvax))))));
    }

    // ---------- the sealed operations pass ----------

    function test_SealedDepositAndWithdraw() public {
        _deposit(lendAvax, 100_000 * E6, _list(lendAvax));
        assertEq(lendAvax.getUserSupplied(address(safe), address(usdc)), 100_000 * E6);

        _run(address(lendAvax), _withdraw(40_000 * E6, address(safe)), _list(lendAvax));
        assertEq(lendAvax.getUserSupplied(address(safe), address(usdc)), 60_000 * E6);
        assertEq(usdc.balanceOf(address(safe)), 940_000 * E6);
    }

    function test_AmountIsFreeButAssetAndRecipientArePinned() public view {
        bytes32 small = module.leafOf(address(lendAvax), _supply(1), PIN_ASSET_AND_RECIPIENT);
        bytes32 big = module.leafOf(address(lendAvax), _supply(1e30), PIN_ASSET_AND_RECIPIENT);
        bytes memory elsewhere = abi.encodeCall(MiniLend.supply, (address(usdc), 1, stranger));
        assertEq(small, big);
        assertTrue(small != module.leafOf(address(lendAvax), elsewhere, PIN_ASSET_AND_RECIPIENT));
    }

    // ---------- everything else is refused, with no effect ----------

    function test_RefusesTransferToUnknownAddress() public {
        // brief, page 3: "send 500,000 USDC to 0x9c…f1", proven with the neighbors of a real operation
        bytes memory data = abi.encodeCall(IERC20.transfer, (stranger, 500_000 * E6));
        bytes32[] memory proof = _proofOf(_list(lendAvax), _leafSupply(lendAvax));
        _expectRefused(address(usdc), data, PIN_FIRST, proof);
        vm.prank(operator);
        module.execute(address(usdc), data, PIN_FIRST, proof);
    }

    function test_RefusesWithdrawToAnotherRecipient() public {
        _deposit(lendAvax, 100_000 * E6, _list(lendAvax));
        bytes memory data = _withdraw(100_000 * E6, stranger);
        bytes32[] memory proof = _proofOf(_list(lendAvax), _leafWithdraw(lendAvax));
        _expectRefused(address(lendAvax), data, PIN_ASSET_AND_RECIPIENT, proof);
        vm.prank(operator);
        module.execute(address(lendAvax), data, PIN_ASSET_AND_RECIPIENT, proof);
    }

    function test_RefusesProtocolNotChecked() public {
        bytes memory data = _supply(100_000 * E6);
        bytes32[] memory proof = _proofOf(_list(lendAvax), _leafSupply(lendAvax));
        _expectRefused(address(lendEth), data, PIN_ASSET_AND_RECIPIENT, proof);
        vm.prank(operator);
        module.execute(address(lendEth), data, PIN_ASSET_AND_RECIPIENT, proof);
    }

    function test_NothingPassesBeforeSealing() public {
        SealedListModule fresh = new SealedListModule(address(safe), operator);
        bytes memory data = _supply(1);
        bytes32 leaf = fresh.leafOf(address(lendAvax), data, PIN_ASSET_AND_RECIPIENT);
        vm.expectRevert(abi.encodeWithSelector(SealedListModule.NotInSealedList.selector, leaf, leaf, bytes32(0)));
        vm.prank(operator);
        fresh.execute(address(lendAvax), data, PIN_ASSET_AND_RECIPIENT, new bytes32[](0));
    }

    function test_ProtocolRevertUndoesTheCall() public {
        bytes memory data = _withdraw(1, address(safe)); // nothing supplied yet
        bytes32[] memory proof = _proofOf(_list(lendAvax), _leafWithdraw(lendAvax));
        vm.expectRevert(
            abi.encodeWithSelector(
                SealedListModule.CallFailed.selector,
                abi.encodeWithSignature("Error(string)", "MiniLend: insufficient balance")
            )
        );
        vm.prank(operator);
        module.execute(address(lendAvax), data, PIN_ASSET_AND_RECIPIENT, proof);
    }

    // ---------- only the front door changes the list ----------

    function test_OnlyOperatorExecutes() public {
        bytes32[] memory proof = _proofOf(_list(lendAvax), _leafApprove(lendAvax));
        vm.expectRevert(SealedListModule.OnlyOperator.selector);
        vm.prank(stranger);
        module.execute(address(usdc), _approve(lendAvax, 1), PIN_FIRST, proof);
    }

    function test_OnlyTheSafeSetsTheRootOrOperator() public {
        vm.startPrank(operator);
        vm.expectRevert(SealedListModule.OnlySafe.selector);
        module.setRoot(bytes32(uint256(1)));
        vm.expectRevert(SealedListModule.OnlySafe.selector);
        module.setOperator(operator);
        vm.stopPrank();
        vm.prank(manager); // the manager's own address is not the Safe: it must sign a Safe transaction
        vm.expectRevert(SealedListModule.OnlySafe.selector);
        module.setRoot(bytes32(uint256(1)));
    }

    function test_OnlyTheManagerSignatureSeals() public {
        bytes32 root = _root(_list(lendEth));
        bytes memory data = abi.encodeCall(SealedListModule.setRoot, (root));
        (, uint256 strangerKey) = makeAddrAndKey("notAnOwner");
        vm.expectRevert(bytes("GS026")); // a signature from anyone but the owner
        this.safeTxSignedBy(address(module), data, strangerKey);
        assertTrue(_safeTx(address(module), data));
        assertEq(module.root(), root);
    }

    function test_ResealToAddAProtocol() public {
        bytes32[] memory both = _concat(_list(lendAvax), _list(lendEth));
        assertTrue(_safeTx(address(module), abi.encodeCall(SealedListModule.setRoot, (_root(both)))));
        _deposit(lendEth, 50_000 * E6, both);
        assertEq(lendEth.getUserSupplied(address(safe), address(usdc)), 50_000 * E6);
    }

    function test_SafeAndModuleAreNeverTargetsEvenIfSealed() public {
        // a careless list that seals a call on the Safe itself and on the module: still refused
        bytes memory addOwner = abi.encodeWithSignature("addOwnerWithThreshold(address,uint256)", stranger, 1);
        bytes memory reseal = abi.encodeCall(SealedListModule.setRoot, (bytes32(0)));
        bytes32[] memory careless = new bytes32[](2);
        careless[0] = module.leafOf(address(safe), addOwner, 0);
        careless[1] = module.leafOf(address(module), reseal, 0);
        assertTrue(_safeTx(address(module), abi.encodeCall(SealedListModule.setRoot, (_root(careless)))));

        vm.startPrank(operator);
        vm.expectRevert(abi.encodeWithSelector(SealedListModule.ForbiddenTarget.selector, address(safe)));
        module.execute(address(safe), addOwner, 0, _proofOf(careless, careless[0]));
        vm.expectRevert(abi.encodeWithSelector(SealedListModule.ForbiddenTarget.selector, address(module)));
        module.execute(address(module), reseal, 0, _proofOf(careless, careless[1]));
        vm.stopPrank();
        assertEq(safe.getOwners().length, 1);
    }

    // ---------- helpers: calldata and leaves ----------

    function _approve(MiniLend m, uint256 amount) internal pure returns (bytes memory) {
        return abi.encodeCall(IERC20.approve, (address(m), amount));
    }

    /// @dev the market is the call target, not an argument
    function _supply(uint256 amount) internal view returns (bytes memory) {
        return abi.encodeCall(MiniLend.supply, (address(usdc), amount, address(safe)));
    }

    function _withdraw(uint256 amount, address to) internal view returns (bytes memory) {
        return abi.encodeCall(MiniLend.withdraw, (address(usdc), amount, to));
    }

    function _leafApprove(MiniLend m) internal view returns (bytes32) {
        return module.leafOf(address(usdc), _approve(m, 0), PIN_FIRST);
    }

    function _leafSupply(MiniLend m) internal view returns (bytes32) {
        return module.leafOf(address(m), _supply(0), PIN_ASSET_AND_RECIPIENT);
    }

    function _leafWithdraw(MiniLend m) internal view returns (bytes32) {
        return module.leafOf(address(m), _withdraw(0, address(safe)), PIN_ASSET_AND_RECIPIENT);
    }

    /// @dev what ticking one protocol adds to the list
    function _list(MiniLend m) internal view returns (bytes32[] memory leaves) {
        leaves = new bytes32[](3);
        leaves[0] = _leafApprove(m);
        leaves[1] = _leafSupply(m);
        leaves[2] = _leafWithdraw(m);
    }

    function _deposit(MiniLend m, uint256 amount, bytes32[] memory leaves) internal {
        _run(address(usdc), _approve(m, amount), leaves, PIN_FIRST);
        _run(address(m), _supply(amount), leaves);
    }

    function _run(address target, bytes memory data, bytes32[] memory leaves) internal {
        _run(target, data, leaves, PIN_ASSET_AND_RECIPIENT);
    }

    function _run(address target, bytes memory data, bytes32[] memory leaves, uint256 pinMask) internal {
        bytes32[] memory proof = _proofOf(leaves, module.leafOf(target, data, pinMask));
        vm.prank(operator);
        module.execute(target, data, pinMask, proof);
    }

    function _expectRefused(address target, bytes memory data, uint256 pinMask, bytes32[] memory proof) internal {
        bytes32 leaf = module.leafOf(target, data, pinMask);
        vm.expectRevert(
            abi.encodeWithSelector(
                SealedListModule.NotInSealedList.selector, leaf, module.processProof(proof, leaf), module.root()
            )
        );
    }

    // ---------- helpers: the Merkle tree, same algorithm as sealed/tree.py ----------

    function _hashPair(bytes32 a, bytes32 b) internal pure returns (bytes32) {
        return a < b ? keccak256(abi.encode(a, b)) : keccak256(abi.encode(b, a));
    }

    function _sorted(bytes32[] memory leaves) internal pure returns (bytes32[] memory out) {
        out = new bytes32[](leaves.length);
        for (uint256 i; i < leaves.length; ++i) {
            bytes32 x = leaves[i];
            uint256 j = i;
            for (; j > 0 && out[j - 1] > x; --j) {
                out[j] = out[j - 1];
            }
            out[j] = x;
        }
    }

    /// @dev sorted leaves, pairs hashed bottom-up, an odd node is carried up unchanged
    function _tree(bytes32[] memory leaves, bytes32 leaf) internal pure returns (bytes32 root, bytes32[] memory proof) {
        bytes32[] memory layer = _sorted(leaves);
        uint256 index = type(uint256).max;
        for (uint256 i; i < layer.length; ++i) {
            if (layer[i] == leaf) index = i;
        }
        bytes32[] memory path = new bytes32[](16);
        uint256 depth;
        while (layer.length > 1) {
            if (index != type(uint256).max) {
                if ((index ^ 1) < layer.length) path[depth++] = layer[index ^ 1];
                index /= 2;
            }
            bytes32[] memory next = new bytes32[]((layer.length + 1) / 2);
            for (uint256 i; i < next.length; ++i) {
                next[i] = 2 * i + 1 < layer.length ? _hashPair(layer[2 * i], layer[2 * i + 1]) : layer[2 * i];
            }
            layer = next;
        }
        root = layer[0];
        proof = new bytes32[](depth);
        for (uint256 i; i < depth; ++i) {
            proof[i] = path[i];
        }
    }

    function _root(bytes32[] memory leaves) internal pure returns (bytes32 root) {
        (root,) = _tree(leaves, bytes32(0));
    }

    function _proofOf(bytes32[] memory leaves, bytes32 leaf) internal pure returns (bytes32[] memory proof) {
        (, proof) = _tree(leaves, leaf);
    }

    function _concat(bytes32[] memory a, bytes32[] memory b) internal pure returns (bytes32[] memory out) {
        out = new bytes32[](a.length + b.length);
        for (uint256 i; i < a.length; ++i) {
            out[i] = a[i];
        }
        for (uint256 i; i < b.length; ++i) {
            out[a.length + i] = b[i];
        }
    }

    // ---------- helpers: the asset manager signs (EIP-712 SafeTx hash) ----------

    function safeTxSignedBy(address to, bytes memory data, uint256 key) external returns (bool) {
        return _safeTxSignedBy(to, data, key);
    }

    function _safeTx(address to, bytes memory data) internal returns (bool) {
        return _safeTxSignedBy(to, data, managerKey);
    }

    function _safeTxSignedBy(address to, bytes memory data, uint256 key) internal returns (bool) {
        bytes32 hash =
            safe.getTransactionHash(to, 0, data, Enum.Operation.Call, 0, 0, 0, address(0), address(0), safe.nonce());
        (uint8 v, bytes32 r, bytes32 s) = vm.sign(key, hash);
        return safe.execTransaction(
            to, 0, data, Enum.Operation.Call, 0, 0, 0, address(0), payable(address(0)), abi.encodePacked(r, s, v)
        );
    }
}
