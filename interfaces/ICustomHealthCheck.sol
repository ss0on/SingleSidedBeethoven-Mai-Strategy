// SPDX-License-Identifier: GPL-3.0

pragma solidity 0.6.12;

interface ICustomHealthCheck {
    function check(
        address callerStrategy,
        uint256 profit,
        uint256 loss,
        uint256 debtPayment,
        uint256 debtOutstanding
    ) external view returns (bool);
}
