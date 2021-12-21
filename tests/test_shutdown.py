# TODO: Add tests that show proper operation of this strategy through "emergencyExit"
#       Make sure to demonstrate the "worst case losses" as well as the time it takes

from brownie import ZERO_ADDRESS
import pytest


def test_vault_shutdown_can_withdraw(
    chain, token, vault, strategy, user, amount, RELATIVE_APPROX
):
    ## Deposit in Vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount

    if token.balanceOf(user) > 0:
        token.transfer(ZERO_ADDRESS, token.balanceOf(user), {"from": user})

    # Harvest 1: Send funds through the strategy
    strategy.harvest()
    chain.mine(1)
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    ## Set Emergency
    vault.setEmergencyShutdown(True)

    ## Withdraw (does it work, do you get what you expect)
    vaultShares = vault.balanceOf(user)
    maxLoss = 100 # 1% BPS
    vault.withdraw(vaultShares, user, maxLoss,{"from": user})

    assert pytest.approx(token.balanceOf(user), rel=RELATIVE_APPROX) == amount


def test_basic_shutdown(
    chain, token, vault, strategy, user, strategist, amount, RELATIVE_APPROX
):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    assert token.balanceOf(vault.address) == amount

    # Harvest 1: Send funds through the strategy
    strategy.harvest()
    chain.mine(1)
    slippage = amount - strategy.estimatedTotalAssets()
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == amount

    ## Earn interest
    strategy.harvest()
    chain.mine(1)
    
    
    # Harvest 2: Realize profit
    strategy.harvest()
    chain.mine(1)
    
    assert vault.totalAssets() >= amount
    assert strategy.estimatedTotalAssets() > amount - slippage
    ## Set emergency
    strategy.setEmergencyExit({"from": strategist})

    strategy.harvest()  ## Remove funds from strategy

    assert strategy.estimatedTotalAssets() == 0
    assert token.balanceOf(strategy) == 0
    ## due to slippage on the way in and the way out we do not have all the funds in the vault
    # assert vault.totalAssets() >= strategyAssets  ## The vault has all funds
    assert pytest.approx(vault.totalAssets(), rel=RELATIVE_APPROX) == amount

