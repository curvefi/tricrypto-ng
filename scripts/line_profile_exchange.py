import boa

from scripts.compile_contracts import INITIAL_PRICES, deploy
from tests.utils.tokens import mint_for_testing


def main():
    boa.env.enable_gas_profiling()

    swap, _, _, _, coins = deploy(optimized=True)
    
    trader = boa.env.generate_address()
    lp = boa.env.generate_address()
    boa.env.set_balance(trader, 10**22)

    quantities = [
        10 ** 6 * 10 ** 36 // p for p in [10 ** 18] + INITIAL_PRICES
    ]

    for user in [trader, lp]:
        for coin in coins:
            mint_for_testing(coin, user, 10**25)
            with boa.env.prank(user):
                coin.approve(swap, 2**256 - 1)

    # Very first deposit
    with boa.env.prank(lp):
        swap.add_liquidity(quantities, 0)

    with boa.env.prank(trader):
        swap.exchange(0, 1, 10**18, 0)
        
    line_profile = swap.line_profile().summary()
    print(line_profile)  # it should die here because too many computations


if __name__ == "__main__":
    main()
