// SPDX-License-Identifier: AGPL-3.0

pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

import {IERC20} from "@openzeppelin/contracts/token/ERC20/SafeERC20.sol";

interface IBalancerPool is IERC20 {
    enum SwapKind {GIVEN_IN, GIVEN_OUT}

    struct SwapRequest {
        SwapKind kind;
        IERC20 tokenIn;
        IERC20 tokenOut;
        uint256 amount;
        // Misc data
        bytes32 poolId;
        uint256 lastChangeBlock;
        address from;
        address to;
        bytes userData;
    }

    function getPoolId() external view returns (bytes32 poolId);

    function symbol() external view returns (string memory s);

    function getRate() external view returns (uint256);

    // function onSwap(
    //     SwapRequest memory swapRequest,
    //     uint256 balanceTokenIn,
    //     uint256 balanceTokenOut
    // ) external view returns (uint256 amount);
    function onSwap(
        SwapRequest memory swapRequest,
        uint256[] memory balances,
        uint256 indexIn,
        uint256 indexOut
    ) external view returns (uint256 amount);
}
