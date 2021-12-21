import brownie
import pytest

import util

# Passing but dangerous maxLoss
def test_operation(
    chain, token, vault, strategy, user, amount, RELATIVE_APPROX
):
    # Deposit to the vault
    user_balance_before = token.balanceOf(user)
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount

    # harvest
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # tend()
    strategy.tend()

    # withdrawal
    vaultShares = vault.balanceOf(user)
    maxLoss = 100 # 1% BPS
    vault.withdraw(vaultShares, user, maxLoss,{"from": user})
    assert (
        pytest.approx(token.balanceOf(user), rel=RELATIVE_APPROX) == user_balance_before
    )

def test_emergency_exit(
        chain, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX
):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    strategy.harvest({"from": strategist})
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # set emergency and exit
    strategy.setEmergencyExit()
    chain.sleep(1)
    strategy.harvest({"from": strategist})
    assert strategy.estimatedTotalAssets() < amount


def test_profitable_harvest(
        chain, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX,  qiDaoToken, qiToken_whale
):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount

    # Harvest 1: Send funds through the strategy
    chain.mine(1)
    strategy.harvest({"from": strategist})
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    before_pps = vault.pricePerShare()

    # Harvest 2: Realize profit
    time = 86400 * 20 # 2 week of running the strategy
    util.airdrop_rewards(amount, time, strategy, qiDaoToken, qiToken_whale)
    strategy.harvest({"from": strategist})  
    chain.sleep(3600 * 6)  # 6 hrs needed for profits to unlock
    chain.mine(1)

    profit = vault.totalAssets() - amount   # Profits go to vault

    assert strategy.estimatedTotalAssets() + profit  > amount
    assert vault.totalAssets() > amount
    assert vault.pricePerShare() > before_pps

def test_deposit_all(chain, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX, gov, qiDaoToken, qiToken_whale):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    strategy.harvest({"from": strategist})
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    chain.sleep(strategy.minDepositPeriod() + 1)
    chain.mine(1)
    while strategy.tendTrigger(0) == True:
        strategy.tend({'from': gov})
        util.stateOfStrat("tend", strategy, token)
        assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount
        chain.sleep(strategy.minDepositPeriod() + 1)
        chain.mine(1)

    time = 86400 * 15  # 2 weeks of running the strategy
    util.airdrop_rewards(amount, time, strategy, qiDaoToken, qiToken_whale)
    before_pps = vault.pricePerShare()

    # Harvest 2: Realize profit
    chain.sleep(1)
    strategy.harvest({"from": strategist})
    chain.sleep(3600 * 6)  # 6 hrs needed for profits to unlock
    chain.mine(1)
    profit = token.balanceOf(vault.address)  # Profits go to vault

    slippageIn = amount * strategy.maxSlippageIn() / 10_000
    assert strategy.estimatedTotalAssets() + profit > (amount - slippageIn)
    assert vault.pricePerShare() > before_pps

    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    chain.sleep(1)
    strategy.harvest({"from": strategist})
    util.stateOfStrat("after harvest 5000", strategy, token)

    half = int(amount / 2)
    # profits
    assert vault.totalAssets() >= amount + profit
    assert vault.totalDebt() >= half
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == half - slippageIn


def test_change_debt( chain, gov, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    chain.sleep(1)
    strategy.harvest({"from": strategist})
    half = int(amount / 2)

    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == half

    vault.updateStrategyDebtRatio(strategy.address, 10_000, {"from": gov})
    chain.sleep(1)
    strategy.harvest({"from": strategist})
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    chain.sleep(1)
    strategy.harvest({"from": strategist})
    util.stateOfStrat("after harvest 5000", strategy, token)

    # compounded slippage
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == half

    vault.updateStrategyDebtRatio(strategy.address, 0, {"from": gov})
    chain.sleep(1)
    strategy.harvest({"from": strategist})
    util.stateOfStrat("after harvest", strategy, token)

    assert token.balanceOf(vault.address) >= amount or pytest.approx(token.balanceOf(vault.address),
                                                                     rel=RELATIVE_APPROX) >= amount



def test_profitability_of_strategy(
    chain, token, vault, strategy, user, amount, RELATIVE_APPROX, qiDaoToken, qiToken_whale
):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    strategy.harvest()
    strategyStartAssets = strategy.estimatedTotalAssets()
    slippageLosses = amount - strategyStartAssets
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    # Harvest 2: Realize profit
    time = 3600 * 24 * 7 # 1 week of running the strategy
    util.airdrop_rewards(amount, time, strategy, qiDaoToken, qiToken_whale)
    strategy.harvest()
    chain.mine(1)

    strategy.harvest()
    strategyActualAssets = strategy.estimatedTotalAssets()
    strategyAssetsIncrement =  strategyActualAssets - strategyStartAssets

    assert vault.totalAssets() > amount
    # Make sure the Annualized APR is bigger than 20%
    assert ((vault.totalAssets() - amount) / amount * 24 * 365 * 100) > 20
    # strategy has more assets than when it started
    assert strategyActualAssets > strategyStartAssets
    # Slippage loss should be less than 1%
    assert slippageLosses / amount * 100 < 1
    # After aprox two week of operations we should have recoup the slippage loss
    # 2 week to be extra careful on the tests and not make the test flaky
    assert strategyAssetsIncrement * 24 * 14 > slippageLosses


def test_change_debt(
    chain, gov, token, vault, strategy, user, amount, RELATIVE_APPROX
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    chain.sleep(1)
    strategy.harvest()
    half = int(amount / 2)

    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == half

    vault.updateStrategyDebtRatio(strategy.address, 10_000, {"from": gov})
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    chain.sleep(1)
    strategy.harvest()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == half


def test_sweep(gov, vault, strategy, token, user, userWithWeth, amount, weth):
    # Strategy want token doesn't work
    token.transfer(strategy, amount, {"from": user})
    assert token.address == strategy.want()
    assert token.balanceOf(strategy) > 0
    with brownie.reverts("!want"):
        strategy.sweep(token, {"from": gov})

    # Vault share token doesn't work
    with brownie.reverts("!shares"):
        strategy.sweep(vault.address, {"from": gov})

    # Protected token doesn't work
    # with brownie.reverts("!protected"):
    #     strategy.sweep(strategy.protectedToken(), {"from": gov})

    before_balance = weth.balanceOf(gov)
    transferAmount = 1000*1e18
    weth.transfer(strategy, transferAmount, {"from": userWithWeth})
    assert weth.address != strategy.want()
    assert weth.balanceOf(user) == 0
    strategy.sweep(weth, {"from": gov})
    assert weth.balanceOf(gov) == transferAmount + before_balance

# TODO: check the tend trigger function bcs it is not working
def test_triggers(
        chain, gov, vault, strategy, token, amount, user,strategist, qiDaoToken, qiToken_whale
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    vault.updateStrategyDebtRatio(strategy.address, 5_000, {"from": gov})
    chain.sleep(1)
    strategy.harvest({"from": strategist})
    
    assert strategy.harvestTrigger(0) == True # The slippage will make the harvestTrigger return true
    time = 86400 * 15 # 1 week of running the strategy
    util.airdrop_rewards(amount, time, strategy, qiDaoToken, qiToken_whale)
    assert strategy.harvestTrigger(0) == True

    assert strategy.tendTrigger(0) == False
   
    chain.sleep(strategy.minDepositPeriod() + 1)
    chain.mine(1)
   
    assert strategy.tendTrigger(0) == False # there is not tend function override

