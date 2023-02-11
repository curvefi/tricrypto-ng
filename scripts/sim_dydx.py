import random

import boa
import click
import pandas as pd
from eth_utils import to_checksum_address

INITIAL_PRICES = [10**18, 47500 * 10**18, 1500 * 10**18]
PARAMS = {
    "A": 135 * 3**3 * 10000,
    "gamma": int(7e-5 * 1e18),
    "mid_fee": int(4e-4 * 1e10),
    "out_fee": int(4e-3 * 1e10),
    "allowed_extra_profit": 2 * 10**12,
    "fee_gamma": int(0.01 * 1e18),
    "adjustment_step": int(0.0015 * 1e18),
    "ma_time": 866,  # 600 seconds / ln(2)
    "initial_prices": INITIAL_PRICES[1:],
}


def mint_for_testing(token_contract, addr, amount, mint_eth=False):

    addr = to_checksum_address(addr)

    if token_contract.symbol() == "WETH":
        boa.env.set_balance(addr, boa.env.get_balance(addr) + amount)
        if not mint_eth:
            with boa.env.prank(addr):
                token_contract.deposit(value=amount)
    else:
        token_contract.eval(f"self.totalSupply += {amount}")
        token_contract.eval(f"self.balanceOf[{addr}] += {amount}")
        token_contract.eval(f"log Transfer(empty(address), {addr}, {amount})")


def _get_deposit_amounts(amount_per_token_usd, initial_prices, coins):

    precisions = [10 ** coin.decimals() for coin in coins]

    deposit_amounts = [
        amount_per_token_usd * precision * 10**18 // price
        for price, precision in zip(initial_prices, precisions)
    ]
    return deposit_amounts


def _get_price(x1, x2, x3, D, gamma, A):

    a = (
        D**9 * (1 + gamma) * (-1 + gamma * (-2 + (-1 + 27 * A) * gamma))
        + 81
        * D**6
        * (1 + gamma * (2 + gamma + 9 * A * gamma))
        * x1
        * x2
        * x3
        - 2187 * D**3 * (1 + gamma) * x1**2 * x2**2 * x3**2
        + 19683 * x1**3 * x2**3 * x3**3
    )
    b = 729 * A * D**5 * gamma**2 * x1 * x2 * x3
    c = 27 * A * D**8 * gamma**2 * (1 + gamma)

    return (x2 * (a - b * (x2 + x3) - c * (2 * x1 + x2 + x3))) / (
        x1 * (-a + b * (x1 + x3) + c * (x1 + 2 * x2 + x3))
    )


def _get_dydx(swap, i, j):

    ANN = swap.A()
    A = ANN / 10**4 / 3**3
    gamma = swap.gamma() / 10**18

    xp = swap.internal.xp()

    for k in range(3):
        if k != i and k != j:
            break

    x1 = xp[i] / 1e18
    x2 = xp[j] / 1e18
    x3 = xp[k] / 1e18

    D = swap.D() / 1e18

    return _get_price(x1, x2, x3, D, gamma, A)


def _get_prices_math(swap):

    # invert to get dx/dy, else it returns dy/dx
    return [
        abs(1 / _get_dydx(swap, 0, 1) * swap.price_scale(0) / 1e18),
        abs(1 / _get_dydx(swap, 0, 2) * swap.price_scale(1) / 1e18),
    ]


def _get_prices_numeric(swap, views):

    smol_dx = 10**18
    return [
        smol_dx / views.get_dy(0, 1, smol_dx, swap),
        smol_dx / views.get_dy(0, 2, smol_dx, swap),
    ]


def _setup_pool():

    deployer = boa.env.generate_address()
    fee_receiver = boa.env.generate_address()
    user = boa.env.generate_address()

    with boa.env.prank(deployer):

        # tokens:
        weth = boa.load("contracts/mocks/WETH.vy")
        usd = boa.load("contracts/mocks/ERC20Mock.vy", "USD", "USD", 18)
        btc = boa.load("contracts/mocks/ERC20Mock.vy", "BTC", "BTC", 18)

        coins = [usd, btc, weth]

        math_contract = boa.load("contracts/CurveCryptoMathOptimized3.vy")

        gauge_interface = boa.load_partial("contracts/LiquidityGauge.vy")
        gauge_implementation = gauge_interface.deploy_as_blueprint()

        amm_interface = boa.load_partial(
            "contracts/CurveTricryptoOptimizedWETH.vy"
        )
        amm_implementation = amm_interface.deploy_as_blueprint()

        views = boa.load(
            "contracts/CurveCryptoViews3Optimized.vy",
            math_contract,
        )

        factory_nofee = boa.load(
            "contracts/CurveTricryptoFactoryNoFee.vy",
            fee_receiver,
            deployer,
            weth,
            math_contract,
        )

        factory_nofee.set_pool_implementation(amm_implementation)
        factory_nofee.set_gauge_implementation(gauge_implementation)
        factory_nofee.set_views_implementation(views)

        _swap = factory_nofee.deploy_pool(
            "Curve.fi USDC-BTC-ETH",
            "USDCBTCETH",
            [coin.address for coin in coins],
            PARAMS["A"],
            PARAMS["gamma"],
            0,
            0,
            0,
            PARAMS["allowed_extra_profit"],
            PARAMS["adjustment_step"],
            PARAMS["ma_time"],
            PARAMS["initial_prices"],
        )
        swap = amm_interface.at(_swap)

    # add 1M of each token to the pool
    quantities = _get_deposit_amounts(10**8, INITIAL_PRICES, coins)

    for coin, quantity in zip(coins, quantities):
        # mint coins for user:
        user_balance = coin.balanceOf(user)
        mint_for_testing(coin, user, quantity)
        assert coin.balanceOf(user) == user_balance + quantity

        # approve crypto_swap to trade coin for user:
        with boa.env.prank(user):
            coin.approve(swap, 2**256 - 1)

    # Very first deposit
    with boa.env.prank(user):
        swap.add_liquidity(quantities, 0)

    # we need to disable loss calculation since there is no fee involved
    # and swaps will not result in vprice going up. to do this, ramp
    # up but do not actually ramp.
    with boa.env.prank(deployer):

        swap.ramp_A_gamma(
            swap.A(),
            swap.gamma(),
            boa.env.vm.state.timestamp + 60 * 60 * 24 * 7 + 1,
        )

    return swap, coins, views


@click.command()
@click.option("--num_samples", default=10)
def main(num_samples):

    swap_nofee, coins, views = _setup_pool()
    swapper = boa.env.generate_address()
    with boa.env.prank(swapper):
        coins[0].approve(swap_nofee, 2**256 - 1)

    mint_for_testing(coins[0], swapper, 10**70)

    init_dydx_math = _get_prices_math(swap_nofee)
    init_dydx_numeric = _get_prices_numeric(swap_nofee, views)

    # sanity check
    for i in range(2):
        assert abs(init_dydx_math[i] - init_dydx_numeric[i]) < 1e-5

    data = {
        "dollar_amt_in": [],
        "price_btc_math": [],
        "price_btc_numeric": [],
        "price_eth_math": [],
        "price_eth_numeric": [],
    }
    while num_samples > 0:

        num_samples -= 1
        coin_out_index = random.randint(1, 2)

        dollar_amount_in = random.randint(1, 8 * 10**7)
        dx = dollar_amount_in * 10**18

        with boa.env.prank(swapper), boa.env.anchor():
            try:
                swap_nofee.exchange(0, coin_out_index, dx, 0)
            except:  # noqa: E722
                continue

            dydx_math = _get_prices_math(swap_nofee)
            dydx_numeric = _get_prices_numeric(swap_nofee, views)

        data["dollar_amt_in"].append(dollar_amount_in)
        data["price_btc_math"].append(dydx_math[0])
        data["price_btc_numeric"].append(dydx_numeric[0])
        data["price_eth_math"].append(dydx_math[1])
        data["price_eth_numeric"].append(dydx_numeric[1])

    # save data
    data = pd.DataFrame(data)
    data.to_csv("data/dydx.csv", index=False)


if __name__ == "__main__":
    main()
