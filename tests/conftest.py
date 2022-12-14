import boa
import pytest

from tests.utils.tokens import mint_for_testing

pytest_plugins = [
    "tests.fixtures.accounts",
    "tests.fixtures.tokens",
    "tests.fixtures.functions",
]
INITIAL_PRICES = [10**18, 47500 * 10**18, 1500 * 10**18]


def pytest_addoption(parser):
    parser.addoption("--optimized", action="store", default="True")


@pytest.fixture(scope="session")
def optimized(request):
    return request.config.getoption("--optimized") == "True"


@pytest.fixture(scope="module", autouse=True)
def tricrypto_lp_token_init(deployer):
    with boa.env.prank(deployer):
        return boa.load(
            "contracts/old/CurveTokenV4.vy",
            "Curve USD-BTC-ETH",
            "crvUSDBTCETH",
        )


@pytest.fixture(scope="module")
def tricrypto_pool_init_params(optimized):
    ma_time = 600  # 10 minutes
    if optimized:
        ma_time = 866  # 600 / ln(2)

    return {
        "A": 135 * 3**3 * 10000,
        "gamma": int(7e-5 * 1e18),
        "mid_fee": int(4e-4 * 1e10),
        "out_fee": int(4e-3 * 1e10),
        "allowed_extra_profit": 2 * 10**12,
        "fee_gamma": int(0.01 * 1e18),
        "adjustment_step": int(0.0015 * 1e18),
        "admin_fee": 0,
        "ma_time": ma_time,
        "initial_prices": INITIAL_PRICES[1:],
    }


@pytest.fixture(scope="module")
def tricrypto_math(deployer, optimized):
    if optimized:
        with boa.env.prank(deployer):
            return boa.load("contracts/CurveCryptoMathOptimized3.vy")
    return boa.load("contracts/old/CurveCryptoMath3.vy")


@pytest.fixture(scope="module")
def tricrypto_views_init(deployer, tricrypto_math):
    with boa.env.prank(deployer):
        return boa.load("contracts/old/CurveCryptoViews3.vy", tricrypto_math)


def _compiled_swap(
    coins, tricrypto_math, tricrypto_lp_token, tricrypto_views, optimized
):

    path = "contracts/old/CurveCryptoSwap.vy"
    if optimized:
        path = "contracts/CurveTricryptoOptimized.vy"

    with open(path, "r") as f:
        source = f.read()
        source = source.replace(
            "0x0000000000000000000000000000000000000000",
            tricrypto_math.address,
        )

        if not optimized:
            # optimized tricrypto is an lp token, but unoptimized
            # needs the lp token contract:
            source = source.replace(
                "0x0000000000000000000000000000000000000001",
                tricrypto_lp_token.address,
            )

            # in optimized contract, views is not used, but there is
            # a commented out line where the views addr can be mentioned
            # since view contract will be deployed anyway:
            source = source.replace(
                "0x0000000000000000000000000000000000000002",
                tricrypto_views.address,
            )

        source = source.replace(
            "0x0000000000000000000000000000000000000010", coins[0].address
        )
        source = source.replace(
            "0x0000000000000000000000000000000000000011", coins[1].address
        )
        source = source.replace(
            "0x0000000000000000000000000000000000000012", coins[2].address
        )

        source = source.replace(
            "1,  # 0", str(10 ** (18 - coins[0].decimals())) + ","
        )
        source = source.replace(
            "1,  # 1", str(10 ** (18 - coins[1].decimals())) + ","
        )
        source = source.replace(
            "1,  # 2", str(10 ** (18 - coins[2].decimals())) + ","
        )
        return source


def _crypto_swap(
    compiled_swap,
    tricrypto_lp_token,
    owner,
    fee_receiver,
    tricrypto_pool_init_params,
    deployer,
    optimized,
):

    with boa.env.prank(deployer):
        swap = boa.loads(
            compiled_swap,
            owner,
            fee_receiver,
            tricrypto_pool_init_params["A"],
            tricrypto_pool_init_params["gamma"],
            tricrypto_pool_init_params["mid_fee"],
            tricrypto_pool_init_params["out_fee"],
            tricrypto_pool_init_params["allowed_extra_profit"],
            tricrypto_pool_init_params["fee_gamma"],
            tricrypto_pool_init_params["adjustment_step"],
            tricrypto_pool_init_params["admin_fee"],
            tricrypto_pool_init_params["ma_time"],
            tricrypto_pool_init_params["initial_prices"],
        )
        if not optimized:
            tricrypto_lp_token.set_minter(swap.address)

    return swap


@pytest.fixture(scope="module", autouse=True)
def tricrypto_swap(
    owner,
    fee_receiver,
    tricrypto_pool_init_params,
    tricrypto_lp_token_init,
    tricrypto_math,
    tricrypto_views_init,
    coins,
    deployer,
    optimized,
):

    source = _compiled_swap(
        coins,
        tricrypto_math,
        tricrypto_lp_token_init,
        tricrypto_views_init,
        optimized,
    )

    return _crypto_swap(
        source,
        tricrypto_lp_token_init,
        owner,
        fee_receiver,
        tricrypto_pool_init_params,
        deployer,
        optimized,
    )


@pytest.fixture(scope="module")
def tricrypto_views(
    tricrypto_views_init, deployer, tricrypto_math, tricrypto_swap, optimized
):
    if not optimized:
        return tricrypto_views_init

    # optimized views is just views with self.swap set up, hence we need to
    # deploy it AFTER swap is deployed
    with boa.env.prank(deployer):
        return boa.load(
            "contracts/CurveCryptoViews3Optimized.vy",
            tricrypto_math,
            tricrypto_swap,
        )


@pytest.fixture(scope="module", autouse=True)
def tricrypto_lp_token(tricrypto_swap, tricrypto_lp_token_init, optimized):
    if optimized:
        return tricrypto_swap  # since optimized contract is also an lp token
    return tricrypto_lp_token_init


def _get_deposit_amounts(amount_per_token_usd, initial_prices, coins):

    precisions = [10 ** coin.decimals() for coin in coins]

    deposit_amounts = [
        amount_per_token_usd * precision * 10**18 // price
        for price, precision in zip(initial_prices, precisions)
    ]
    return deposit_amounts


def _crypto_swap_with_deposit(coins, user, tricrypto_swap, initial_prices):

    # add 1M of each token to the pool
    quantities = _get_deposit_amounts(10**6, initial_prices, coins)

    for coin, quantity in zip(coins, quantities):
        # mint coins for user:
        mint_for_testing(coin, user, quantity)
        assert coin.balanceOf(user) == quantity

        # approve crypto_swap to trade coin for user:
        with boa.env.prank(user):
            coin.approve(tricrypto_swap, 2**256 - 1)

    # Very first deposit
    with boa.env.prank(user):
        tricrypto_swap.add_liquidity(quantities, 0)

    return tricrypto_swap


@pytest.fixture(scope="module")
def tricrypto_swap_with_deposit(tricrypto_swap, coins, user):
    yield _crypto_swap_with_deposit(
        coins, user, tricrypto_swap, INITIAL_PRICES
    )
