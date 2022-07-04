import boa
import pytest


INITIAL_PRICES = [1, 20000, 1100]  # in usdt
INITIAL_DEPOSITS = 3 * 10**6  # 3M usdt worth


def _format_addr(t):
    if isinstance(t, str):
        t = t.encode("utf-8")
    return t.rjust(20, b"\x00")


@pytest.fixture(scope="module")
def owner():
    yield _format_addr("fiddy")


@pytest.fixture(scope="module")
def fee_receiver():
    yield _format_addr("ecb")


@pytest.fixture(scope="module")
def user():
    yield _format_addr("user")


@pytest.fixture(scope="module", autouse=True)
def crypto_math():
    yield boa.load("contracts/CurveCryptoMath3.vy")


@pytest.fixture(scope="module")
def weth():
    yield boa.load("contracts/mocks/WETH.vy")


@pytest.fixture(scope="module")
def coins(weth):
    pool_coins = []
    pool_coins.append(boa.load("contracts/mocks/ERC20Mock.vy", "USDT", "USDT", 6))
    pool_coins.append(boa.load("contracts/mocks/ERC20Mock.vy", "WBTC", "WBTC", 8))
    pool_coins.append(weth)
    yield pool_coins


@pytest.fixture(scope="module", autouse=True)()
def crypto_views(crypto_math, coins):
    path = "contracts/CurveCryptoViews3.vy"
    with open(path, "r") as f:
        source = f.read()
        source = source.replace("1,#0", str(10 ** (18 - coins[0].decimals())) + ",")
        source = source.replace("1,#1", str(10 ** (18 - coins[1].decimals())) + ",")
        source = source.replace("1,#2", str(10 ** (18 - coins[2].decimals())) + ",")
    yield boa.loads(source, crypto_math)


@pytest.fixture(scope="module", autouse=True)
def token():
    yield boa.load(
        "contracts/mocks/CurveTokenV4.vy", "Curve USD-BTC-ETH", "crvUSDBTCETH"
    )


@pytest.fixtyre(scope="module")
def pool_params():
    yield {
        "A": 135 * 3**3 * 10000,
        "gamma": int(7e-5 * 1e18),
        "mid_fee": int(4e-4 * 1e10),
        "out_fee": int(4e-3 * 1e10),
        "allowed_extra_profit": 2 * 10**12,
        "fee_gamma": int(0.01 * 1e18),
        "adjustment_step": int(0.0015 * 1e18),
        "admin_fee": 0,
        "ma_half_time": 600,
    }


@pytest.fixture(scope="module", autouse=True)
def crypto_swap(
    crypto_math, token, crypto_views, coins, owner, fee_receiver, pool_params
):
    path = "contracts/CurveCryptoSwap.vy"
    with open(path, "r") as f:
        source = f.read()
        source = source.replace(
            "0x0000000000000000000000000000000000000000", crypto_math.address
        )
        source = source.replace(
            "0x0000000000000000000000000000000000000001", token.address
        )
        source = source.replace(
            "0x0000000000000000000000000000000000000002", crypto_views.address
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

        source = source.replace("1,#0", str(10 ** (18 - coins[0].decimals())) + ",")
        source = source.replace("1,#1", str(10 ** (18 - coins[1].decimals())) + ",")
        source = source.replace("1,#2", str(10 ** (18 - coins[2].decimals())) + ",")

    yield boa.loads(source, owner, fee_receiver, *pool_params, INITIAL_PRICES)


@pytest.fixture(scope="module")
def crypto_swap_with_deposit(crypto_swap, coins, user):
    quantities = []
    for idx, coin in enumerate(coins):
        quantity = INITIAL_DEPOSITS[idx] / INITIAL_PRICES[idx] * 10 ** coin.decimals()
        quantities.append(quantity)

        # mint coins for user:
        coin._mint_for_testing(user, quantity)
        assert coin.balanceOf(user) == quantity

        # approve crypto_swap to trade coin for user:
        with boa.env.prank(user):
            coin.approve(crypto_swap, 2**256 - 1)

    # Very first deposit
    with boa.env.prank(user):
        crypto_swap.add_liquidity(quantities, 0)

    return crypto_swap


@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass
