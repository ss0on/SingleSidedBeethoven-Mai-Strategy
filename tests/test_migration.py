import pytest
from conftest import deployStrategy


def test_funds_migration(
    chain,
    token,
    vault,
    strategy,
    amount,
    Strategy,
    strategist,
    gov,
    user,
    RELATIVE_APPROX,
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    strategy.harvest()
    estimatedTotalAssets = strategy.estimatedTotalAssets()
    assert pytest.approx(estimatedTotalAssets, rel=RELATIVE_APPROX) == amount
    rewards = strategy.balanceOfReward()
    balanceOfBptInMasterChef = strategy.balanceOfBptInMasterChef()
    balanceOfStakeBptInMasterChef = strategy.balanceOfStakeBptInMasterChef()
    # deploy new strategy
    new_strategy = deployStrategy(Strategy, strategist, gov, vault)
    # migrate to a new strategy
    vault.migrateStrategy(strategy, new_strategy, {"from": gov})

    # assert that the old strategy does not have any funds
    assert (strategy.estimatedTotalAssets() == 0)
    assert (strategy.balanceOfBpt() == 0)
    assert (strategy.balanceOfBptInMasterChef() == 0)
    assert (strategy.balanceOfStakeBptInMasterChef() == 0)
    assert (strategy.balanceOfReward() == 0)

    # assert that all the funds ( want, stake, bpt and rewards) have been migrated correctly
    assert (new_strategy.estimatedTotalAssets() == estimatedTotalAssets)
    assert (new_strategy.balanceOfStakeBptInMasterChef() >= balanceOfStakeBptInMasterChef)
    assert (new_strategy.balanceOfBpt() >= balanceOfBptInMasterChef)
    assert (new_strategy.balanceOfReward() >= rewards)

def test_funds_migration_and_user_withdraw(
    chain,
    token,
    vault,
    strategy,
    amount,
    Strategy,
    strategist,
    gov,
    user,
    RELATIVE_APPROX,
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    strategy.harvest()
    estimatedTotalAssets = strategy.estimatedTotalAssets()
    assert pytest.approx(estimatedTotalAssets, rel=RELATIVE_APPROX) == amount

    # deploy new strategy
    new_strategy = deployStrategy(Strategy, strategist, gov, vault)
    # migrate to a new strategy
    vault.migrateStrategy(strategy, new_strategy, {"from": gov})

    vault.withdraw(amount, user, 55, {"from": user})

    userBalance = token.balanceOf(user)

    # assert that all the funds ( want, stake, bpt and rewards) have been withdraw correctly
    assert pytest.approx(userBalance, rel=RELATIVE_APPROX) == userBalance
    assert (new_strategy.estimatedTotalAssets() == 0)
    assert (new_strategy.balanceOfStakeBptInMasterChef() == 0)
    assert (new_strategy.balanceOfBptInMasterChef() == 0)
    assert (new_strategy.balanceOfReward() == 0)

def test_new_strategy_after_migration(
    chain,
    token,
    vault,
    strategy,
    amount,
    Strategy,
    strategist,
    gov,
    user,
    RELATIVE_APPROX,
):
    # Deposit to the vault and harvest
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    strategy.harvest()
    estimatedTotalAssets = strategy.estimatedTotalAssets()
    assert pytest.approx(estimatedTotalAssets, rel=RELATIVE_APPROX) == amount
    strategyStaked =  strategy.balanceOfStakeBptInMasterChef()

    # deploy new strategy
    new_strategy = deployStrategy(Strategy, strategist, gov, vault)
    new_strategy.setKeeper(gov)

    assert (strategy.address != new_strategy.address)
    # migrate to a new strategy
    vault.migrateStrategy(strategy, new_strategy, {"from": gov})

    assert (strategy.estimatedTotalAssets() == 0)
    assert (new_strategy.estimatedTotalAssets() >= estimatedTotalAssets)

    startTotalAssets = new_strategy.estimatedTotalAssets()
    vaultStartTotalAssets = vault.totalAssets()

    # run strategy to make sure we are still earning money
    chain.mine(10)
    new_strategy.harvest()

    assert (vault.totalAssets() > vaultStartTotalAssets)
    assert (new_strategy.estimatedTotalAssets() > 0)

    chain.mine(10)
    new_strategy.harvest()

    finalTotalAssets = new_strategy.estimatedTotalAssets()
    assert (new_strategy.balanceOfStakeBptInMasterChef() >= strategyStaked)
    # The results may vary depending on the slippage and deposit fee
    assert pytest.approx(finalTotalAssets, rel=RELATIVE_APPROX) == startTotalAssets
    assert pytest.approx(finalTotalAssets, rel=RELATIVE_APPROX) == estimatedTotalAssets
