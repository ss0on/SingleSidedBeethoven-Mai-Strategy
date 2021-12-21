from brownie import Contract

def stateOfStrat(msg, strategy, token):
    print(f'\n===={msg}====')
    wantDec = 10 ** token.decimals()
    print(f'Balance of {token.symbol()}: {strategy.balanceOfWant() / wantDec}')
    print(f'Balance of Bpt: {strategy.balanceOfBpt() / wantDec}')
    print(f'Estimated Total Assets: {strategy.estimatedTotalAssets() / wantDec}')

# Beethoven uses blocks count to give rewards so the Chain.sleep() method of timetravel does not work
# Chain.mine() is too slow so the best solution is to airdrop rewards
def airdrop_rewards(amount , time, strategy, qiDaoToken, qiToken_whale):
    APY =  0.2
    timeRatio = time / (86400 * 365)
    qiDaoToken.approve(strategy, 2 ** 256 - 1, {'from': qiToken_whale})
    qiDaoToken.transfer(strategy, amount  * 1e12 * APY * timeRatio , {'from': qiToken_whale})