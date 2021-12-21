from pathlib import Path
import sys
import os

from brownie import Strategy, accounts, config, network, project, web3, CommonHealthCheck
from eth_utils import is_checksum_address
import click

script_dir = os.path.dirname( __file__ )
strategyConfig_dir = os.path.join( script_dir )
sys.path.append( strategyConfig_dir )

import strategyConfig

API_VERSION = config["dependencies"][0].split("@")[-1]
Vault = project.load(
    Path.home() / ".brownie" / "packages" / config["dependencies"][0]
).Vault


def get_address(msg: str, default: str = None) -> str:
    val = click.prompt(msg, default=default)

    # Keep asking user for click.prompt until it passes
    while True:

        if is_checksum_address(val):
            return val
        elif addr := web3.ens.address(val):
            click.echo(f"Found ENS '{val}' [{addr}]")
            return addr

        click.echo(
            f"I'm sorry, but '{val}' is not a checksummed address or valid ENS record"
        )
        # NOTE: Only display default once
        val = click.prompt(msg)


def main():
    print(f"You are using the '{network.show_active()}' network")
    gov = accounts[0]
    print(f"You are using: 'dev' [{gov.address}]")

    vault = Vault.at("0x162A433068F51e18b7d13932F27e66a3f99E6890")

    print(
        f"""

        Strategy Parameters

        api: {API_VERSION}
        vault: {vault}
        token: {vault.token()}
        name: '{vault.name()}'
        symbol: '{vault.symbol()}'

        """
    )

    strategy = deploy(Strategy, gov, gov, vault)
   
    print(
        f"""

        Strategy

        address: {strategy}

        """
    )
    debt_ratio = 10_000 # 100%
    minDebtPerHarvest = 0  # Lower limit on debt add
    maxDebtPerHarvest = 1_000_000_000_000 # Upper limit on debt add
    performance_fee = 0 # Strategist perf fee: 10%
   
    vault.addStrategy(
      strategy,
      debt_ratio,
      minDebtPerHarvest,
      maxDebtPerHarvest,
      performance_fee,
      {"from":gov}
    )

    addHealthCheck(strategy, gov, gov)
    


def addHealthCheck(strategy, gov, deployer):
    healthCheck = CommonHealthCheck.deploy({"from":deployer})
    healthCheck.setGovernance(gov, {"from":deployer})
    healthCheck.setManagement(gov, {"from":deployer})
    strategy.setHealthCheck(healthCheck,{"from":deployer})

    return healthCheck

def deploy(Strategy, deployer, gov ,vault):
    config = strategyConfig.getStrategyConfig("MAI_Concerto_staking", vault)

    deployArgs = config["deployArgs"]
    stakeParams = config["stakeParams"]
    whitelistReward = config["whitelistReward"]
    stakeInfo = config["stakeInfo"]

    strategy = Strategy.deploy(*deployArgs, {"from": deployer})
    strategy.setStakeParams(stakeParams[0],stakeParams[1], {"from": gov})
    strategy.whitelistReward( 
        whitelistReward["rewardToken"], 
        whitelistReward["steps"],
        {"from": gov}
    )
    strategy.setStakeInfo(
        stakeInfo["assets"], 
        stakeInfo["stakePool"],
        stakeInfo["stakeTokenIndex"], 
        stakeInfo["stakeWantIndex"], 
        stakeInfo["masterChefStakePoolId"], 
        {"from": gov}
    )
    
    return strategy
    
