import boa
import pytest

from tests.utils import mine
from tests.utils.tokens import mint_for_testing

pytest_plugins = [
    "fixtures.accounts",
    "fixtures.tokens",
    "fixtures.functions",
]
INITIAL_PRICES = [47500 * 10**18, 1500 * 10**18]


def pytest_addoption(parser):
    parser.addoption("--optimized", action="store", default="True")


@pytest.fixture(scope="session")
def optimized(request):
    return request.config.getoption("--optimized") == "True"


@pytest.fixture(scope="module", autouse=True)
def tricrypto_lp_token(deployer):
    with boa.env.prank(deployer), mine():
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
    }


@pytest.fixture(scope="module")
def tricrypto_math(deployer, optimized):
    if optimized:
        with boa.env.prank(deployer), mine():
            return boa.load("contracts/CurveCryptoMathOptimized3.vy")
    return boa.load("contracts/old/CurveCryptoMath3.vy")


@pytest.fixture(scope="module")
def tricrypto_views(deployer, tricrypto_math):
    with boa.env.prank(deployer), mine():
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
        source = source.replace(
            "0x0000000000000000000000000000000000000001",
            tricrypto_lp_token.address,
        )
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
            "1,#0", str(10 ** (18 - coins[0].decimals())) + ","
        )
        source = source.replace(
            "1,#1", str(10 ** (18 - coins[1].decimals())) + ","
        )
        source = source.replace(
            "1,#2", str(10 ** (18 - coins[2].decimals())) + ","
        )
        return source


def _crypto_swap(
    compiled_swap,
    tricrypto_lp_token,
    owner,
    fee_receiver,
    tricrypto_pool_init_params,
    deployer,
):

    with boa.env.prank(deployer), mine():
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
            INITIAL_PRICES,
        )

        tricrypto_lp_token.set_minter(swap.address)

    return swap


@pytest.fixture(scope="module", autouse=True)
def tricrypto_swap(
    owner,
    fee_receiver,
    tricrypto_pool_init_params,
    tricrypto_lp_token,
    tricrypto_math,
    tricrypto_views,
    coins,
    deployer,
    optimized,
):

    source = _compiled_swap(
        coins, tricrypto_math, tricrypto_lp_token, tricrypto_views, optimized
    )

    return _crypto_swap(
        source,
        tricrypto_lp_token,
        owner,
        fee_receiver,
        tricrypto_pool_init_params,
        deployer,
    )


def _crypto_swap_with_deposit(coins, user, tricrypto_swap):
    # add 1M of each token to the pool
    quantities = [
        10**6 * 10**36 // p for p in [10**18] + INITIAL_PRICES
    ]  # $3M worth

    for coin, quantity in zip(coins, quantities):
        # mint coins for user:
        mint_for_testing(coin, user, quantity)
        assert coin.balanceOf(user) == quantity

        # approve crypto_swap to trade coin for user:
        with boa.env.prank(user):
            coin.approve(tricrypto_swap, 2**256 - 1)

    # Very first deposit
    with boa.env.prank(user), mine():
        tricrypto_swap.add_liquidity(quantities, 0)

    return tricrypto_swap


@pytest.fixture(scope="module")
def tricrypto_swap_with_deposit(tricrypto_swap, coins, user):
    yield _crypto_swap_with_deposit(coins, user, tricrypto_swap)
