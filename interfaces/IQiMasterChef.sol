// SPDX-License-Identifier: AGPL-3.0

pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

import { IERC20 } from '@openzeppelin/contracts/token/ERC20/SafeERC20.sol';

interface IQiMasterChef {
	// Info of each user.
	struct UserInfo {
		uint256 amount; // How many LP tokens the user has provided.
		uint256 rewardDebt; // Reward debt. See explanation below.
		//
		// We do some fancy math here. Basically, any point in time, the amount of ERC20s
		// entitled to a user but is pending to be distributed is:
		//
		//   pending reward = (user.amount * pool.accERC20PerShare) - user.rewardDebt
		//
		// Whenever a user deposits or withdraws LP tokens to a pool. Here's what happens:
		//   1. The pool's `accERC20PerShare` (and `lastRewardBlock`) gets updated.
		//   2. User receives the pending reward sent to his/her address.
		//   3. User's `amount` gets updated.
		//   4. User's `rewardDebt` gets updated.
	}

	// Info of each pool.
	struct PoolInfo {
		IERC20 lpToken; // Address of LP token contract.
		uint256 allocPoint; // How many allocation points assigned to this pool. ERC20s to distribute per block.
		uint256 lastRewardBlock; // Last block number that ERC20s distribution occurs.
		uint256 accERC20PerShare; // Accumulated ERC20s per share, times 1e12.
		uint16 depositFeeBP; // Deposit fee in basis points
	}

	// Info of each user that stakes LP tokens.
	function userInfo(uint256 _pid, address _user) external view returns (uint256 _amountLP, uint256 _rewardDebt);

	// Info of each pool.
	function poolInfo(uint256 _pid) external view returns (PoolInfo memory pInf);

	// Deposit LP tokens to Farm for ERC20 allocation.
	function deposit(uint256 _pid, uint256 _amount) external;

	// Withdraw LP tokens from Farm.
	function withdraw(uint256 _pid, uint256 _amount) external;

	// Withdraw without caring about rewards. EMERGENCY ONLY.
	function emergencyWithdraw(uint256 _pid) external;
}
