// SPDX-License-Identifier: AGPL-3.0

pragma solidity 0.6.12;
pragma experimental ABIEncoderV2;

import { BaseStrategy } from '@yearnvaults/contracts/BaseStrategy.sol';
import { SafeERC20, IERC20, Address } from '@openzeppelin/contracts/token/ERC20/SafeERC20.sol';
import { SafeMath } from '@openzeppelin/contracts/math/SafeMath.sol';
import { ERC20 } from '@openzeppelin/contracts/token/ERC20/ERC20.sol';
import { Math } from '@openzeppelin/contracts/math/Math.sol';

import { IBalancerVault } from '../interfaces/IBalancerVault.sol';
import { IBalancerPool } from '../interfaces/IBalancerPool.sol';
import { IAsset } from '../interfaces/IAsset.sol';
import { IQiMasterChef } from '../interfaces/IQiMasterChef.sol';

/**
 * @title Yearn Beethoven_Mai USDC strategy
 * @author yearn.finance
 * note This strategy uses Beethoven and Mai.finance protocols to generate returns.
 * 			The strategy deposits funds on Beethoven Pools, getting LP tokens in return.
 * 			This LP tokens are then deposited in Mai.finance masterChef to generate QI rewards.
 * 			When the harvest is done:
 *				- Some of the profits are reinvested into another Beethoven Pool with higher yield and then,
 *					into mai.finance masterChef
 *				- The rest of the rewards are converted into want tokens and sent to the vault.
 * note This incurs a fee of 0.5% when depositing funds on mai.finance masterChef.
 * 			This should be taken into account when setting up the vault's withdraw queue,
 *			also when doing withdraw or rebalanced operations.
 */
contract Strategy is BaseStrategy {
	using SafeERC20 for IERC20;
	using Address for address;
	using SafeMath for uint256;

	IBalancerVault public balancerVault;
	IBalancerPool public bpt;
	IERC20 public rewardToken;
	IAsset[] internal assets;
	SwapSteps internal swapSteps;
	uint256[] internal minAmountsOut;
	bytes32 internal balancerPoolId;
	uint8 internal numTokens;
	uint8 internal tokenIndex;
	uint256 internal wantDecimals;
	bool internal abandonRewards;

	IQiMasterChef internal masterChef;

	IAsset[] internal stakeAssets;
	IBalancerPool public stakeBpt;
	uint256 internal stakeTokenIndex;
	uint256 internal stakeWantIndex;
	uint256 internal stakePercentage;
	uint256 internal unstakePercentage;

	struct SwapSteps {
		bytes32[] poolIds;
		IAsset[] assets;
	}

	// uint256 internal constant max = type(uint256).max;

	//	   1	0.01%
	//	   5	0.05%
	//    10	0.1%
	//    50	0.5%
	//   100	1%
	//  1000	10%
	// 10000	100%
	uint256 public maxSlippageIn; // bips
	uint256 public maxSlippageOut; // bips
	uint256 public maxSingleDeposit;
	uint256 public minDepositPeriod; // seconds
	uint256 public lastDepositTime;
	bytes32 internal stakePoolId;
	uint256 internal masterChefPoolId;
	uint256 internal masterChefStakePoolId;
	uint256 internal constant basisOne = 10000;

	constructor(
		address _vault,
		address _balancerVault,
		address _balancerPool,
		address _masterChef,
		uint256 _maxSlippageIn,
		uint256 _maxSlippageOut,
		uint256 _maxSingleDeposit,
		uint256 _minDepositPeriod,
		uint256 _masterChefPoolId
	) public BaseStrategy(_vault) {
		bpt = IBalancerPool(_balancerPool);
		balancerPoolId = bpt.getPoolId();
		balancerVault = IBalancerVault(_balancerVault);
		(IERC20[] memory tokens, , ) = balancerVault.getPoolTokens(balancerPoolId);
		numTokens = uint8(tokens.length);
		assets = new IAsset[](numTokens);
		tokenIndex = type(uint8).max;
		for (uint8 i = 0; i < numTokens; i++) {
			if (tokens[i] == want) {
				tokenIndex = i;
			}
			assets[i] = IAsset(address(tokens[i]));
		}
		require(tokenIndex != type(uint8).max, 'token not in pool!');
		wantDecimals = ERC20(address(want)).decimals();
		maxSlippageIn = _maxSlippageIn;
		maxSlippageOut = _maxSlippageOut;
		maxSingleDeposit = _maxSingleDeposit.mul(10**uint256(wantDecimals));
		minAmountsOut = new uint256[](numTokens);
		minDepositPeriod = _minDepositPeriod;
		masterChefPoolId = _masterChefPoolId;

		masterChef = IQiMasterChef(_masterChef);
		IQiMasterChef.PoolInfo memory poolInfo = masterChef.poolInfo(masterChefPoolId);
		require(address(poolInfo.lpToken) == address(bpt));

		want.safeApprove(address(balancerVault), type(uint256).max);
		bpt.approve(address(masterChef), type(uint256).max);
	}

	//--------------------------//
	// 			 Public Methods 		//
	//--------------------------//

	/**
	 * Provide an accurate estimate for the total amount of assets
	 * (principle + return) that this Strategy is currently managing,
	 * denominated in terms of `want` tokens.
	 * This function is only use for an approximation and does not influence the vault logic.
	 	note Do not add the staked assets bcs/ they are unrealized gains from a volatile token
				they will added once they become "realized" next harvest.	
	 */
	function estimatedTotalAssets() public view override returns (uint256) {
		return balanceOfWant().add(balanceOfPooled());
	}

	function ethToWant(uint256 _amtInWei) public view override returns (uint256) {}

	function tendTrigger(uint256 callCostInWei) public view override returns (bool) {
		return now.sub(lastDepositTime) > minDepositPeriod && balanceOfWant() > 0;
	}

	function balanceOfWant() public view returns (uint256 _amount) {
		return want.balanceOf(address(this));
	}

	function balanceOfBpt() public view returns (uint256 _amount) {
		return bpt.balanceOf(address(this));
	}

	function balanceOfBptInMasterChef() public view returns (uint256 _amount) {
		(_amount, ) = masterChef.userInfo(masterChefPoolId, address(this));
	}

	function totalBalanceOfBpt() public view returns (uint256 _amount) {
		return balanceOfBpt().add(balanceOfBptInMasterChef());
	}

	function balanceOfStakeBptInMasterChef() public view returns (uint256 _amount) {
		(_amount, ) = masterChef.userInfo(masterChefStakePoolId, address(this));
	}

	function balanceOfReward() public view returns (uint256 _amount) {
		return rewardToken.balanceOf(address(this));
	}

	/**
	 * Provide an accurate estimate for the total amount of assets
	 * on Beethoven pools and QI masterChef,
	 * denominated in terms of `want` tokens.
	 */
	function balanceOfPooled() public view returns (uint256 _amount) {
		uint256 totalWantPooled;
		(IERC20[] memory tokens, uint256[] memory totalBalances, uint256 lastChangeBlock) =
			balancerVault.getPoolTokens(balancerPoolId);
		for (uint8 i = 0; i < numTokens; i++) {
			uint256 tokenPooled = totalBalances[i].mul(totalBalanceOfBpt()).div(bpt.totalSupply());
			if (tokenPooled > 0) {
				IERC20 token = tokens[i];
				if (token != want) {
					IBalancerPool.SwapRequest memory request =
						IBalancerPool.SwapRequest(
							IBalancerPool.SwapKind.GIVEN_IN,
							token,
							want,
							tokenPooled,
							balancerPoolId,
							lastChangeBlock,
							address(this),
							address(this),
							abi.encode(0)
						);
					// now denominated in want
					tokenPooled = bpt.onSwap(request, totalBalances, i, tokenIndex);
				}
				totalWantPooled += tokenPooled;
			}
		}
		return totalWantPooled;
	}

	/**
	 * Swap step inside Beethoven the strategy is using
	 * to convert rewards into want token
	 */
	function getSwapSteps() public view returns (SwapSteps memory) {
		return swapSteps;
	}

	//--------------------------//
	// 			External Methods 		//
	//--------------------------//

	function name() external view override returns (string memory) {
		return string(abi.encodePacked('SingleSidedBeethoven ', bpt.symbol(), 'Pool ', ERC20(address(want)).symbol()));
	}

	receive() external payable {}

	//--------------------------//
	// 			Internal Methods 		//
	//--------------------------//

	/**
	 * Perform any Strategy unwinding or other calls necessary to capture the
	 * "free return" this Strategy has generated since the last time its core
	 * position(s) were adjusted.
	 */
	function prepareReturn(uint256 _debtOutstanding)
		internal
		override
		returns (
			uint256 _profit,
			uint256 _loss,
			uint256 _debtPayment
		)
	{
		if (_debtOutstanding > 0) {
			(_debtPayment, _loss) = liquidatePosition(_debtOutstanding);
		}

		uint256 beforeWant = balanceOfWant();

		collectTradingFees();
		// Claim QI
		claimAllRewards();
		// Consolidate % to stake and unStake
		consolidate();
		// Sell the % not staked
		sellRewards();

		_profit = balanceOfWant().sub(beforeWant);
		if (_profit > _loss) {
			_profit = _profit.sub(_loss);
			_loss = 0;
		} else {
			_loss = _loss.sub(_profit);
			_profit = 0;
		}
	}

	/**
	 * Used to invest funds into the protocols ( Beethoven and QI DAO)
	 * @param _debtOutstanding: debt we have to pay the vault.
	 */
	function adjustPosition(uint256 _debtOutstanding) internal override {
		if (now - lastDepositTime < minDepositPeriod) {
			return;
		}

		// Put want into lp then put want-lp into masterChef
		uint256 pooledBefore = balanceOfPooled();
		uint256 amountIn = Math.min(maxSingleDeposit, balanceOfWant());
		if (joinPool(amountIn, assets, numTokens, tokenIndex, balancerPoolId)) {
			// Put all want-lp into masterChef
			masterChef.deposit(masterChefPoolId, balanceOfBpt());

			uint256 pooledDelta = balanceOfPooled().sub(pooledBefore);
			uint256 joinSlipped = amountIn > pooledDelta ? amountIn.sub(pooledDelta) : 0;

			require(joinSlipped <= amountIn.mul(maxSlippageIn).div(basisOne), 'Slipped in!');
			lastDepositTime = now;
		} else if (balanceOfBpt() > 0) {
			masterChef.deposit(masterChefPoolId, balanceOfBpt());
		}

		// Claim all QI rewards.
		claimAllRewards();
		// Consolidate instead of stake all, in case the strategy is setup to not stake.
		consolidate();
	}

	/**
	 * Liquidate a position from masterChef and Pools
	 * The operation will revert if the slippage is greater than the set values.
	 * note Deposits on MAI.finance masterChef have a 0.5% fee,
	 * 			so we should only withdraw from masterChef what is strictly necessary.
	 * note The wantToLPAmount is not exact so should be used with care and with tolerances.
	 */
	function liquidatePosition(uint256 _amountNeeded)
		internal
		override
		returns (uint256 _liquidatedAmount, uint256 _loss)
	{
		if (estimatedTotalAssets() < _amountNeeded) {
			_liquidatedAmount = liquidateAllPositions();
			return (_liquidatedAmount, _amountNeeded.sub(_liquidatedAmount));
		}

		uint256 looseAmount = balanceOfWant();
		if (_amountNeeded > looseAmount) {
			uint256 toExitAmount = _amountNeeded.sub(looseAmount);

			// Withdraw ONLY the needed bpt out of masterChef
			masterChef.withdraw(masterChefPoolId, wantToLPAmount(toExitAmount));
			// Sell some bpt
			exitPoolExactToken(toExitAmount);
			// Put remaining bpt back into masterChef
			masterChef.deposit(masterChefPoolId, balanceOfBpt());

			_liquidatedAmount = Math.min(balanceOfWant(), _amountNeeded);
			_loss = _amountNeeded.sub(_liquidatedAmount);

			_enforceSlippageOut(toExitAmount, _liquidatedAmount.sub(looseAmount));
		} else {
			_liquidatedAmount = _amountNeeded;
		}
	}

	/**
	 * Convert want amount to LP amount.
	 * This operation is not exact so should be used with extra care.
	 * The return _lpAmount has a value of at least the _wantAmount
	 * @param _wantAmount : amount of want to convert to lp
	 * @return _lpAmount : amount of lp tokens equal to the want amount
	 */
	function wantToLPAmount(uint256 _wantAmount) public view returns (uint256 _lpAmount) {
		_lpAmount = _wantAmount.mul(10**wantDecimals).div(balanceOfPooled()).mul(totalBalanceOfBpt()).div(10**wantDecimals);
	}

	/**
	 * Liquidate all position from masterChef and Pools
	 * The operation will revert if the slippage is greater than the set values.
	 */
	function liquidateAllPositions() internal override returns (uint256 liquidated) {
		uint256 eta = estimatedTotalAssets();
		// Withdraw all bpt out of masterChef
		// Withdraw main bpt pool
		withdrawAndHarvest(masterChefPoolId, balanceOfBptInMasterChef());
		// Withdraw staked bpt pool
		withdrawAndHarvest(masterChefStakePoolId, balanceOfStakeBptInMasterChef());

		// Sell all bpt for want
		exitPoolExactBpt(balanceOfBpt(), assets, tokenIndex, balancerPoolId, minAmountsOut);
		// Exit all staked bpt and get want token
		exitPoolExactBpt(
			stakeBpt.balanceOf(address(this)),
			stakeAssets,
			stakeWantIndex,
			stakePoolId,
			new uint256[](stakeAssets.length)
		);
		// Sell all the claimed and unStaked rewards for want
		sellRewards();

		liquidated = balanceOfWant();
		_enforceSlippageOut(eta, liquidated);

		return liquidated;
	}

	/**
	 * This method withdraws assets (reward + LP) into newStrategy.
	 */
	function prepareMigration(address _newStrategy) internal override {
		_withdrawFromMasterChef(_newStrategy);
		if (balanceOfReward() > 0) {
			rewardToken.transfer(_newStrategy, balanceOfReward());
		}
	}

	function protectedTokens() internal view override returns (address[] memory) {}

	/**
	 * This method withdraws assets (stakedLP & LP) from masterChef.
	 * Specify where to withdraw the assets to.
	 * note AbandonRewards withdraws LP without rewards.
	 * note QI masterChef does not allow withdrawing to a new address so we need two steps for it.
	 */
	function _withdrawFromMasterChef(address _to) internal {
		uint256 balanceBptInMasterChef = balanceOfBptInMasterChef();
		if (balanceBptInMasterChef > 0) {
			abandonRewards
				? masterChef.emergencyWithdraw(masterChefPoolId)
				: withdrawAndHarvest(masterChefPoolId, balanceBptInMasterChef);
			bpt.transfer(_to, balanceBptInMasterChef);
		}

		uint256 balanceStakeBptInMasterChef = balanceOfStakeBptInMasterChef();
		if (balanceStakeBptInMasterChef > 0) {
			abandonRewards
				? masterChef.emergencyWithdraw(masterChefStakePoolId)
				: withdrawAndHarvest(masterChefStakePoolId, balanceStakeBptInMasterChef);
			stakeBpt.transfer(_to, balanceStakeBptInMasterChef);
		}
	}

	/**
	 * Harvest all rewards from masterChef.
	 * Withdraw a specific amount of LP from masterChef
	 * note: To harvest all the rewards we need to do a deposit with no amount of LP.
	 *			 https://docs.mai.finance/functions/smart-contract-functions#staking-rewards
	 */
	function withdrawAndHarvest(uint256 _poolId, uint256 _balanceToWithdraw) internal {
		masterChef.deposit(_poolId, 0);
		masterChef.withdraw(_poolId, _balanceToWithdraw);
	}

	/**
	 * Claim all QI rewards from masterChef and stake masterChef
	 * note: To harvest all the rewards we need to do a deposit with no amount of LP.
	 *			 https://docs.mai.finance/functions/smart-contract-functions#staking-rewards
	 */
	function claimAllRewards() internal {
		masterChef.deposit(masterChefPoolId, 0);
		masterChef.deposit(masterChefStakePoolId, 0);
	}

	/**
	 * Sell all the Rewards for want token.
	 * note: The Rewards will only be sold if it economical sense to do so.
	 */
	function sellRewards() internal {
		uint256 amount = balanceOfReward();

		// uint256 decReward = ERC20(address(rewardToken)).decimals();
		// uint256 decWant = ERC20(address(want)).decimals();
		if (amount > 10**12) {
			uint256 length = swapSteps.poolIds.length;
			IBalancerVault.BatchSwapStep[] memory steps = new IBalancerVault.BatchSwapStep[](length);
			int256[] memory limits = new int256[](length + 1);
			limits[0] = int256(amount);
			for (uint256 j = 0; j < length; j++) {
				steps[j] = IBalancerVault.BatchSwapStep(swapSteps.poolIds[j], j, j + 1, j == 0 ? amount : 0, abi.encode(0));
			}
			balancerVault.batchSwap(
				IBalancerVault.SwapKind.GIVEN_IN,
				steps,
				swapSteps.assets,
				IBalancerVault.FundManagement(address(this), false, address(this), false),
				limits,
				now + 10
			);
		}
	}

	/**
	 * This method withdraws assets for masterChef and Pool to collect the profits from trading fees.
	 * note Deposits on MAI.finance masterChef have a 0.5% fee,
	 * 			so we should only withdraw from masterChef what is strictly necessary.
	 * note The wantToLPAmount is not exact so should be used with care and with tolerances.
	 */
	function collectTradingFees() internal {
		uint256 debt = vault.strategies(address(this)).totalDebt;
		if (estimatedTotalAssets() > debt) {
			// Withdraw ONLY the needed bpt out of masterChef
			masterChef.withdraw(masterChefPoolId, wantToLPAmount(estimatedTotalAssets().sub(debt)));
			// Exit pool for the profit amount generated
			exitPoolExactToken(estimatedTotalAssets().sub(debt));
			// Put remaining bpt back into masterChef
			masterChef.deposit(masterChefPoolId, balanceOfBpt());
		}
	}

	/**
	 * Exit Pool position for single token.
	 * Withdraw exact amount of BPT to exit from the pool.
	 * Could revert due to single exit limit enforced by balancer.
	 * @param  _tokenIndex: The index of the token to remove from the pool.
	 * @param  _bpts: Amount of bpts we want to withdraw.
	 */
	function exitPoolExactBpt(
		uint256 _bpts,
		IAsset[] memory _assets,
		uint256 _tokenIndex,
		bytes32 _balancerPoolId,
		uint256[] memory _minAmountsOut
	) internal {
		if (_bpts > 0) {
			bytes memory userData = abi.encode(IBalancerVault.ExitKind.EXACT_BPT_IN_FOR_ONE_TOKEN_OUT, _bpts, _tokenIndex);
			IBalancerVault.ExitPoolRequest memory request =
				IBalancerVault.ExitPoolRequest(_assets, _minAmountsOut, userData, false);
			balancerVault.exitPool(_balancerPoolId, address(this), address(this), request);
		}
	}

	/**
	 * Exit Pool position and gets want token.
	 * Withdraw exact amount of Tokens (want) to get from the pool.
	 * Could revert due to single exit limit enforced by balancer.
	 * @param  _amountTokenOut: Amount of tokens we want to withdraw from the pool.
	 */
	function exitPoolExactToken(uint256 _amountTokenOut) internal {
		uint256[] memory amountsOut = new uint256[](numTokens);
		amountsOut[tokenIndex] = _amountTokenOut;
		bytes memory userData = abi.encode(IBalancerVault.ExitKind.BPT_IN_FOR_EXACT_TOKENS_OUT, amountsOut, balanceOfBpt());
		IBalancerVault.ExitPoolRequest memory request =
			IBalancerVault.ExitPoolRequest(assets, minAmountsOut, userData, false);
		balancerVault.exitPool(balancerPoolId, address(this), address(this), request);
	}

	/**
	 * Join Pool position for single token.
	 * Deposit exact amount of Tokens to the pool.
	 * @param  _tokenIndex: The index of the token to deposit in the pool.
	 * @param  _amountIn: Exact amount of tokens to deposit in the pool.
	 */
	function joinPool(
		uint256 _amountIn,
		IAsset[] memory _assets,
		uint256 _numTokens,
		uint256 _tokenIndex,
		bytes32 _poolId
	) internal returns (bool _joined) {
		uint256[] memory maxAmountsIn = new uint256[](_numTokens);
		maxAmountsIn[_tokenIndex] = _amountIn;
		if (_amountIn > 0) {
			bytes memory userData = abi.encode(IBalancerVault.JoinKind.EXACT_TOKENS_IN_FOR_BPT_OUT, maxAmountsIn, 0);
			IBalancerVault.JoinPoolRequest memory request =
				IBalancerVault.JoinPoolRequest(_assets, maxAmountsIn, userData, false);
			balancerVault.joinPool(_poolId, address(this), address(this), request);
			return true;
		}
		return false;
	}

	/**
	 * Enforce that amount exited didn't slip beyond our tolerance.
	 * Revert if slippage out exceeds our requirement.
	 */
	function _enforceSlippageOut(uint256 _intended, uint256 _actual) internal view {
		// Just in case there's positive slippage
		uint256 exitSlipped = _intended > _actual ? _intended.sub(_actual) : 0;
		require(exitSlipped <= _intended.mul(maxSlippageOut).div(basisOne), 'Slipped');
	}

	/**
	 * Calculate how much QI to unStake and stake.
	 * This function maintains the configure ratio of staked amount.
	 * The % of staked rewards depends on the stakePercentage.
	 */
	function consolidate() internal {
		// UnStake a % of staked beets
		unstake();
		// Stake pre-calc amount of QI for higher apy
		stake(balanceOfReward().mul(stakePercentage).div(basisOne));
	}

	/**
	 * Deposits a certain amount of QI into QI-wFTM beethoven pool.
	 * Then it deposits those LP into mai.finance masterChef.
	 */
	function stake(uint256 _amount) internal {
		if (joinPool(_amount, stakeAssets, stakeAssets.length, stakeTokenIndex, stakePoolId)) {
			masterChef.deposit(masterChefStakePoolId, stakeBpt.balanceOf(address(this)));
		}
	}

	/**
	 * UnStake a % QI-wFTM LP from masterChef.
	 * Then with the UnStaked LP exits pool with the reward token (QI).
	 */
	function unstake() internal {
		uint256 bpts = balanceOfStakeBptInMasterChef().mul(unstakePercentage).div(basisOne);
		withdrawAndHarvest(masterChefStakePoolId, bpts);
		exitPoolExactBpt(bpts, stakeAssets, stakeTokenIndex, stakePoolId, new uint256[](stakeAssets.length));
	}

	//--------------------------//
	// 		Protected Methods 		//
	//--------------------------//

	/**
	 * Used in emergencies.
	 * Manually returns lps in masterChef to the strategy.
	 */
	function emergencyWithdrawFromMasterChef() external onlyVaultManagers {
		_withdrawFromMasterChef(address(this));
	}

	/**
	 * Setups the reward token address.
	 * Approves reward token transfers.
	 * Specifies the steps to to sell this reward token for want tokens
	 */
	function whitelistReward(address _rewardToken, SwapSteps memory _steps) public onlyVaultManagers {
		rewardToken = IERC20(_rewardToken);
		rewardToken.approve(address(balancerVault), type(uint256).max);
		swapSteps = _steps;
	}

	/**
	 * Strategy Params needed for correct operations of this.
	 * Warning!: on the constructor the maxSingle deposited is set without decimal places.
	 * Here it needs decimal places.
	 * @param _maxSingleDeposit: Same decimals as want token
	 */
	function setParams(
		uint256 _maxSlippageIn,
		uint256 _maxSlippageOut,
		uint256 _maxSingleDeposit,
		uint256 _minDepositPeriod
	) public onlyVaultManagers {
		require(_maxSlippageIn <= basisOne);
		maxSlippageIn = _maxSlippageIn;

		require(_maxSlippageOut <= basisOne);
		maxSlippageOut = _maxSlippageOut;

		maxSingleDeposit = _maxSingleDeposit;
		minDepositPeriod = _minDepositPeriod;
	}

	/**
	 * MasterChef contract in case of masterChef migration.
	 */
	function setMasterChef(address _masterChef) public onlyGovernance {
		_withdrawFromMasterChef(address(this));

		bpt.approve(address(masterChef), 0);
		stakeBpt.approve(address(masterChef), 0);
		masterChef = IQiMasterChef(_masterChef);
		bpt.approve(address(masterChef), type(uint256).max);
		stakeBpt.approve(address(masterChef), type(uint256).max);
	}

	/**
	 * Set params for staking %.
	 * This values can greatly influence the APR of the strategy.
	 * @param _stakePercentageBips: 10_000 = 100%
	 *@param _unstakePercentageBips: 10_000 = 100%
	 */
	function setStakeParams(uint256 _stakePercentageBips, uint256 _unstakePercentageBips) public onlyVaultManagers {
		stakePercentage = _stakePercentageBips;
		unstakePercentage = _unstakePercentageBips;
	}

	/**
	 * Set info of where to stake the QI tokens.
	 * Managers can change this to follow optimal yield
	 */
	function setStakeInfo(
		IAsset[] memory _stakeAssets,
		address _stakePool,
		uint256 _stakeTokenIndex,
		uint256 _stakeWantIndex,
		uint256 _masterChefStakePoolId
	) public onlyVaultManagers {
		stakeAssets = _stakeAssets;
		masterChefStakePoolId = _masterChefStakePoolId;
		stakeBpt = IBalancerPool(_stakePool);
		stakePoolId = stakeBpt.getPoolId();
		stakeBpt.approve(address(masterChef), type(uint256).max);
		stakeTokenIndex = _stakeTokenIndex;
		stakeWantIndex = _stakeWantIndex;
	}

	/**
	 * Toggle for whether to abandon rewards or not on emergency withdraws from masterChef.
	 * Managers can change this to follow optimal yield
	 */
	function setAbandonRewards(bool abandon) external onlyVaultManagers {
		abandonRewards = abandon;
	}
}
