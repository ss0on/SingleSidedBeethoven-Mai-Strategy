# masterchefPool Id comes from here -> https://ftmscan.com/address/0x8166994d9ebBe5829EC86Bd81258149B87faCfd3#readContract
# lpToken (5º query ) on read contract 

def getStrategyConfig(strategyName, vault):  

  if(strategyName == "MAI_Concerto"):
    # balancerPool: MAI Concerto ( USDC -> MAI )
    deployArgs = [
      vault, 
      "0x20dd72Ed959b6147912C2e529F0a0C651c33c9ce", # _balancerVault  
      "0x985976228a4685ac4ecb0cfdbeed72154659b6d9", # _balancerPool
      "0x230917f8a262bF9f2C3959eC495b11D1B7E1aFfC", # _masterChef
      5, #_maxSlippageIn 
      5, #_maxSlippageOut
      10000000000000000000000000 , #_maxSingleDeposit
      1800, #_minDepositPeriod
      0, #_masterChefPoolId
    ]
    # Stake 30% of the profits
    stakeParams = [0,0]

    # Reward Token: QI
    # Steps: QI -> wFTM -> USDC ( 2 step swap)
    # Steps Swap Pool: Qi Major -> Fantom Of The Opera

    whitelistReward = {
      "rewardToken": "0x68Aa691a8819B07988B18923F712F3f4C8d36346",
      "steps": (
        [
          "0x7ae6a223cde3a17e0b95626ef71a2db5f03f540a00020000000000000000008a",
          "0xcdf68a4d525ba2e90fe959c74330430a5a6b8226000200000000000000000008"
        ],
        [
          "0x68Aa691a8819B07988B18923F712F3f4C8d36346", # QI ( Reward Token )
          "0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83", # wFTM
          "0x04068DA6C83AFCFA0e13ba15A6696662335D5B75" # USDC ( want token )
        ] 
      )
    }

    # No Stake possible for this strategy
    stakeInfo={}


    return {
      "deployArgs": deployArgs, 
      "stakeParams":  stakeParams, 
      "whitelistReward":  whitelistReward,
      "stakeInfo":  stakeInfo
    }

  if(strategyName == "MAI_Concerto_staking"):
    # balancerPool: MAI Concerto ( USDC -> MAI )
    deployArgs = [
      vault, 
      "0x20dd72Ed959b6147912C2e529F0a0C651c33c9ce", # _balancerVault  
      "0x985976228a4685ac4ecb0cfdbeed72154659b6d9", # _balancerPool
      "0x230917f8a262bF9f2C3959eC495b11D1B7E1aFfC", # _masterChef
      55, #_maxSlippageIn 
      55, #_maxSlippageOut
      1_000_000_000, #_maxSingleDeposit
      3600, #_minDepositPeriod
      0, #_masterChefPoolId
    ]
    # Stake 0% of the profits
    stakeParams = [0,0]

    # Reward Token: QI
    # Steps: QI -> wFTM -> USDC ( 2 step swap)
    # Steps Swap Pool: Qi Major -> Fantom Of The Opera

    whitelistReward = {
      "rewardToken": "0x68Aa691a8819B07988B18923F712F3f4C8d36346",
      "steps": (
        [
          "0x7ae6a223cde3a17e0b95626ef71a2db5f03f540a00020000000000000000008a",
          "0xcdf68a4d525ba2e90fe959c74330430a5a6b8226000200000000000000000008"
        ],
        [
          "0x68Aa691a8819B07988B18923F712F3f4C8d36346", # QI ( Reward Token )
          "0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83", # wFTM
          "0x04068DA6C83AFCFA0e13ba15A6696662335D5B75" # USDC ( want token )
        ] 
      )
    }
    # Stake Info
    # Assets [ wFTM (40%), QI ( 60%)]
    # Stake Pool: Qi Major
    stakeInfo = {
      "assets":["0x21be370D5312f44cB42ce377BC9b8a0cEF1A4C83","0x68Aa691a8819B07988B18923F712F3f4C8d36346"],
      "stakePool": "0x7aE6A223cde3A17E0B95626ef71A2DB5F03F540A",
      "stakeTokenIndex": 1,
      "stakeWantIndex":0,
      "masterChefStakePoolId":1
    }

    return {
      "deployArgs": deployArgs, 
      "stakeParams":  stakeParams, 
      "whitelistReward":  whitelistReward,
      "stakeInfo":  stakeInfo
    }

  return None
  

