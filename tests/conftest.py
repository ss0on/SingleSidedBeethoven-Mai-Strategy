import pytest
from brownie import config, Contract

import sys
import os

script_dir = os.path.dirname( __file__ )
strategyDeploy_dir = os.path.join( script_dir ,  ".." , "scripts" )
sys.path.append( strategyDeploy_dir )

from deployStrategy import addHealthCheck, deploy


@pytest.fixture
def gov(accounts):
    yield accounts[0]

@pytest.fixture
def user(accounts):
    yield accounts[0]

@pytest.fixture
def user2(accounts):
    yield accounts[9]

@pytest.fixture
def user3(accounts):
    yield accounts[7]

@pytest.fixture
def userWithWeth(accounts):
    yield accounts.at("0x39B3bd37208CBaDE74D0fcBDBb12D606295b430a", force=True)


@pytest.fixture
def rewards(accounts):
    yield accounts[1]


@pytest.fixture
def guardian(accounts):
    yield accounts[0]


@pytest.fixture
def management(accounts):
    yield accounts[0]


@pytest.fixture
def strategist(accounts):
    yield accounts[4]


@pytest.fixture
def keeper(accounts):
    yield accounts[0]


@pytest.fixture
def token():
    token_address = "0x04068DA6C83AFCFA0e13ba15A6696662335D5B75"  # this should be the address of the ERC-20 used by the strategy/vault (DAI)
    yield Contract.from_explorer(token_address)

@pytest.fixture
def qiDaoToken():
    token_address = "0x68Aa691a8819B07988B18923F712F3f4C8d36346"
    yield Contract.from_explorer(token_address)

@pytest.fixture
def qiToken_whale(accounts):
    token_address = "0x84B67E43474a403Cde9aA181b02Ba07399a54573"
    return accounts.at(token_address, force=True)


@pytest.fixture
def amount(accounts, token, user):
    amount = 100_000 * 10 ** token.decimals()
    # In order to get some funds for the token you are about to use,
    # it impersonate an exchange address to use it's funds.
    reserve = accounts.at("0x20dd72Ed959b6147912C2e529F0a0C651c33c9ce", force=True)
    token.transfer(user, amount, {"from": reserve})
    yield amount

@pytest.fixture
def amount2(accounts, token, user2):
    amount = 10_000 * 10 ** token.decimals()
    # In order to get some funds for the token you are about to use,
    # it impersonate an exchange address to use it's funds.
    reserve = accounts.at("0x20dd72Ed959b6147912C2e529F0a0C651c33c9ce", force=True)
    token.transfer(user2, amount, {"from": reserve})
    yield amount

@pytest.fixture
def amount3(accounts, token, user3):
    amount = 100_000 * 10 ** token.decimals()
    # In order to get some funds for the token you are about to use,
    # it impersonate an exchange address to use it's funds.
    reserve = accounts.at("0x20dd72Ed959b6147912C2e529F0a0C651c33c9ce", force=True)
    token.transfer(user3, amount, {"from": reserve})
    yield amount


@pytest.fixture
def weth():
    token_address = "0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83"
    yield Contract.from_explorer(token_address)


@pytest.fixture
def weth_amount(user, weth):
    weth_amount = 10 ** weth.decimals()
    user.transfer(weth, weth_amount)
    yield weth_amount


@pytest.fixture
def vault(pm, gov, rewards, guardian, management, token):
    Vault = pm(config["dependencies"][0]).Vault
    vault = guardian.deploy(Vault)
    vault.initialize(token, gov, rewards, "", "", guardian, management)
    vault.setDepositLimit(2 ** 256 - 1, {"from": gov})
    vault.setManagement(management, {"from": gov})
    yield vault


@pytest.fixture
def strategy(strategist, keeper, vault, Strategy, gov):
    strategy = deployStrategy(Strategy, strategist, gov ,vault)
    # strategy = strategist.deploy(Strategy, vault)
    strategy.setKeeper(keeper)
    vault.addStrategy(strategy, 10_000, 0, 2 ** 256 - 1, 1_000, {"from": gov})
    addHealthCheck(strategy, gov, gov)
    yield strategy

def deployStrategy(Strategy, strategist, gov, vault):
    return deploy(Strategy, strategist, gov ,vault)



@pytest.fixture(scope="session")
def RELATIVE_APPROX():
    # this is more permessive due to single sided deposits and pool size which incurres slippage and prize impact
    yield 1e-2 # 0.1% of slippage
