import boa
import pytest

from tests.boa.utils.tokens import mint_for_testing

INITIAL_PRICES = [10**18, 47500 * 10**18, 1500 * 10**18]


def _get_deposit_amounts(amount_per_token_usd, initial_prices, coins):

    precisions = [10 ** coin.decimals() for coin in coins]

    deposit_amounts = [
        amount_per_token_usd * precision * 10**18 // price
        for price, precision in zip(initial_prices, precisions)
    ]
    return deposit_amounts


def _crypto_swap_with_deposit(
    coins, user, tricrypto_swap, initial_prices, dollar_amt_each_coin=10**6
):

    # add 1M of each token to the pool
    quantities = _get_deposit_amounts(
        dollar_amt_each_coin, initial_prices, coins
    )

    for coin, quantity in zip(coins, quantities):
        # mint coins for user:
        user_balance = coin.balanceOf(user)
        mint_for_testing(coin, user, quantity)
        assert coin.balanceOf(user) == user_balance + quantity

        # approve crypto_swap to trade coin for user:
        with boa.env.prank(user):
            coin.approve(tricrypto_swap, 2**256 - 1)

    # Very first deposit
    with boa.env.prank(user):
        tricrypto_swap.add_liquidity(quantities, 0)

    return tricrypto_swap


@pytest.fixture(scope="module")
def params():

    ma_time = 866  # 600 seconds / ln(2)
    return {
        "A": 135 * 3**3 * 10000,
        "gamma": int(7e-5 * 1e18),
        "mid_fee": int(4e-4 * 1e10),
        "out_fee": int(4e-3 * 1e10),
        "allowed_extra_profit": 2 * 10**12,
        "fee_gamma": int(0.01 * 1e18),
        "adjustment_step": int(0.0015 * 1e18),
        "ma_time": ma_time,
        "initial_prices": INITIAL_PRICES[1:],
    }


@pytest.fixture(scope="module")
def swap(
    tricrypto_factory,
    amm_interface,
    coins,
    weth,
    params,
    deployer,
):
    with boa.env.prank(deployer):
        swap = tricrypto_factory.deploy_pool(
            "Curve.fi USDC-BTC-ETH",
            "USDCBTCETH",
            [coin.address for coin in coins],
            weth,
            0,  # <-------- 0th implementation index
            params["A"],
            params["gamma"],
            params["mid_fee"],
            params["out_fee"],
            params["fee_gamma"],
            params["allowed_extra_profit"],
            params["adjustment_step"],
            params["ma_time"],  # <--- no admin_fee needed
            params["initial_prices"],
        )

    return amm_interface.at(swap)


@pytest.fixture(scope="module")
def swap_multiprecision(
    tricrypto_factory,
    amm_interface,
    tricrypto_coins,
    deployer,
    weth,
):

    _params = {
        "A": 1707629,
        "gamma": 11809167828997,
        "mid_fee": 3000000,
        "out_fee": 30000000,
        "allowed_extra_profit": 2000000000000,
        "fee_gamma": 500000000000000,
        "adjustment_step": 490000000000000,
        "ma_time": 600,
        "initial_prices": [21894513622432734092261, 1546874643304938916307],
    }

    with boa.env.prank(deployer):
        swap = tricrypto_factory.deploy_pool(
            "Curve.fi USDT<>WBTC<>ETH",
            "tricrypto3",
            [coin.address for coin in tricrypto_coins],
            weth,
            0,
            _params["A"],
            _params["gamma"],
            _params["mid_fee"],
            _params["out_fee"],
            _params["fee_gamma"],
            _params["allowed_extra_profit"],
            _params["adjustment_step"],
            _params["ma_time"],
            _params["initial_prices"],
        )

    return amm_interface.at(swap)


@pytest.fixture(scope="module")
def hyper_swap(
    tricrypto_factory_experimental,
    hyperamm_interface,
    coins,
    params,
    deployer,
):
    with boa.env.prank(deployer):
        swap = tricrypto_factory_experimental.deploy_pool(
            "Curve.fi USDC-BTC-ETH",
            "USDCBTCETH",
            [coin.address for coin in coins],
            0,  # <-------- 0th implementation index
            params["A"],
            params["gamma"],
            params["mid_fee"],
            params["out_fee"],
            params["fee_gamma"],
            params["allowed_extra_profit"],
            params["adjustment_step"],
            params["ma_time"],  # <--- no admin_fee needed
            params["initial_prices"],
        )

    return hyperamm_interface.at(swap)


@pytest.fixture(scope="module")
def swap_with_deposit(swap, coins, user):
    yield _crypto_swap_with_deposit(coins, user, swap, INITIAL_PRICES)


@pytest.fixture(scope="module")
def hyper_swap_with_deposit(hyper_swap, coins, user):
    yield _crypto_swap_with_deposit(coins, user, hyper_swap, INITIAL_PRICES)


@pytest.fixture(scope="module")
def yuge_swap(swap, coins, user):
    yield _crypto_swap_with_deposit(
        coins, user, swap, INITIAL_PRICES, dollar_amt_each_coin=10**10
    )
