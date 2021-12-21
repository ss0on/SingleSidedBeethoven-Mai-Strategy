import pytest

import util

# Passing but dangerous maxLoss
def test_deposit_withdraw(
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
    maxLoss = 55 # 0.55% BPS
    vault.withdraw(vaultShares, user, maxLoss,{"from": user})
    assert (
        pytest.approx(token.balanceOf(user), rel=RELATIVE_APPROX) == user_balance_before
    )

# Passing but dangerous maxLoss
def test_multiple__harvest_deposits_withdraw(
    chain, token, vault, strategy, user, user2, user3, amount,amount2,amount3, RELATIVE_APPROX, qiDaoToken, qiToken_whale
):
    # Deposit to the vault
    user_1_balance_before = token.balanceOf(user)
    user_2_balance_before = token.balanceOf(user2)
    user_3_balance_before = token.balanceOf(user3)

    totalDeposit = amount + amount2 + amount3

    token.approve(vault.address, amount, {"from": user})
    token.approve(vault.address, amount2, {"from": user2})
    token.approve(vault.address, amount3, {"from": user3})

    vault.deposit(amount, {"from": user})
    vault.deposit(amount2, {"from": user2})
    vault.deposit(amount3, {"from": user3})

    pps_before = vault.pricePerShare()
    assert token.balanceOf(vault.address) ==totalDeposit

    # harvest to deposit funds on the strategy
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()

    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == totalDeposit
    time= 86400* 7 # 1 week of work
    util.airdrop_rewards(amount, time, strategy, qiDaoToken, qiToken_whale)
    # 20% / 52 weeks = 0.38% per week
    assert strategy.estimatedTotalAssets() < totalDeposit # Less than initial deposit
    # harvest to get rewards
    strategy.harvest()
    chain.sleep(3600*6) # 6 hours to unlock profits on the vault
    chain.mine(1)

    maxLoss = 100 # 0.01% BPS
    
    # withdrawal user
    vaultShares = vault.balanceOf(user)
    vault.withdraw(vaultShares, user, maxLoss,{"from": user})

    # withdrawal user2
    vaultShares = vault.balanceOf(user2)
    vault.withdraw(vaultShares, user2, maxLoss,{"from": user2})

    # withdrawal user3
    vaultShares = vault.balanceOf(user3)
    vault.withdraw(vaultShares, user3, 250,{"from": user3})

    assert vault.pricePerShare() > pps_before
    assert token.balanceOf(user) > user_1_balance_before
    assert token.balanceOf(user2) > user_2_balance_before
    # user3 has higher losses due to taking the loss from the other 2 users, up to 3% of losses
    assert pytest.approx(token.balanceOf(user3), rel=0.03) ==  user_3_balance_before

def test_losses_multiple_deposits_withdraw(
    chain, token, vault, strategy, user, user2, user3, amount,amount2,amount3, RELATIVE_APPROX, qiDaoToken, qiToken_whale
):
    # Deposit to the vault
    user_1_balance_before = token.balanceOf(user)
    user_2_balance_before = token.balanceOf(user2)
    user_3_balance_before = token.balanceOf(user3)

    totalDeposit = amount + amount2 + amount3

    token.approve(vault.address, amount, {"from": user})
    token.approve(vault.address, amount2, {"from": user2})
    token.approve(vault.address, amount3, {"from": user3})

    vault.deposit(amount, {"from": user})
    vault.deposit(amount2, {"from": user2})
    vault.deposit(amount3, {"from": user3})

    assert token.balanceOf(vault.address) ==totalDeposit

    # Harvest to deposit funds on the strategy
    chain.sleep(1)
    chain.mine(1)
    strategy.harvest()
    totalDepositLoss = totalDeposit - strategy.estimatedTotalAssets()

    # Losses due to deposit fee and price impact
    assert pytest.approx(strategy.estimatedTotalAssets(), rel=RELATIVE_APPROX) == totalDeposit 

    maxLoss = 1 # 0.01% BPS
    
    # Withdrawal user
    beforeUserWithdrawAssets = strategy.estimatedTotalAssets()
    vaultShares = vault.balanceOf(user)
    vault.withdraw(vaultShares, user, maxLoss,{"from": user})
    # This loss is taken by the users left in the vault.
    userWithdrawLoss = beforeUserWithdrawAssets - (strategy.estimatedTotalAssets() + amount)
    # User has no profit & no loss
    assert token.balanceOf(user) == user_1_balance_before

    # Withdrawal user2
    beforeUser2WithdrawAssets = strategy.estimatedTotalAssets()
    vaultShares = vault.balanceOf(user2)
    vault.withdraw(vaultShares, user2, maxLoss,{"from": user2})
    user2WithdrawLoss = beforeUser2WithdrawAssets - (strategy.estimatedTotalAssets() + amount2)
    # User2 has no profit & no loss
    assert token.balanceOf(user2) == user_2_balance_before

    # Withdrawal user3
    beforeUser3WithdrawAssets = strategy.estimatedTotalAssets()
    beforeWithdrawUser3Assets = token.balanceOf(user3)
    vaultShares = vault.balanceOf(user3)
    vault.withdraw(vaultShares, user3, 120,{"from": user3})
    user3WithdrawAmount = token.balanceOf(user3) - beforeWithdrawUser3Assets
    user3WithdrawLoss = beforeUser3WithdrawAssets - user3WithdrawAmount
    totalUsersWithdrawLoss = userWithdrawLoss + user2WithdrawLoss + user3WithdrawLoss
    user3TotalLoss = user_3_balance_before - token.balanceOf(user3)
    # User2 has no profit but do have loss
    # We need to take into account mng fees and performance fees so it is not exact
    # Deposit Fee for the 3 users + Withdraw slippage for the 3 users
    assert user3WithdrawAmount + totalDepositLoss + totalUsersWithdrawLoss == amount3 
    # User3 will incur higher losses than expected because the instant deposit - withdraw situation.
    # Because the 0.5% deposit fee is not communicated to the vault, the others users will withdraw the exact deposited amount.
    # Since the vault is not aware, the losses are not distributed between all users, just the last one. 
    # That is when vault realizes it does not have enough funds to pay the last user.
    # This means that user3 will take the losses of all the fees and slippages.
    # assert user3TotalLoss < 1.2% of total loss
    assert user3TotalLoss / amount3 < 0.012 # 1.2% of total loss
