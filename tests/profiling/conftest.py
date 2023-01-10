import boa
import pytest

from tests.fixtures.pool import INITIAL_PRICES
from tests.utils.tokens import mint_for_testing


@pytest.fixture(scope="module")
def init_params2():
    ma_time = 600  # 10 minutes
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
def init_params3():
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
def token2(deployer):
    with boa.env.prank(deployer):
        return boa.load(
            "contracts/old/CurveTokenV4.vy",
            "Curve USD-BTC-ETH",
            "crvUSDBTCETH",
            name="TricryptoLPToken",
        )


@pytest.fixture(scope="module")
def math2():
    return boa.load("contracts/old/CurveCryptoMath3.vy", name="TricryptoMath")


@pytest.fixture(scope="module")
def math3(deployer):
    with boa.env.prank(deployer):
        return boa.load(
            "contracts/CurveCryptoMathOptimized3.vy",
            name="TricryptoMathOptimized",
        )


@pytest.fixture(scope="module")
def views2(deployer, math2):
    with boa.env.prank(deployer):
        return boa.load(
            "contracts/old/CurveCryptoViews3.vy", math2, name="TricryptoViews"
        )


@pytest.fixture(scope="module")
def swap2_empty(
    owner,
    fee_receiver,
    init_params2,
    token2,
    math2,
    views2,
    coins,
    deployer,
):
    path = "contracts/old/CurveCryptoSwap.vy"

    with open(path, "r") as f:
        source = f.read()
        source = source.replace(
            "0x0000000000000000000000000000000000000000",
            math2.address,
        )

        source = source.replace(
            "0x0000000000000000000000000000000000000001",
            token2.address,
        )
        source = source.replace(
            "0x0000000000000000000000000000000000000002",
            views2.address,
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

    with boa.env.prank(deployer):
        swap = boa.loads(
            source,
            owner,
            fee_receiver,
            init_params2["A"],
            init_params2["gamma"],
            init_params2["mid_fee"],
            init_params2["out_fee"],
            init_params2["allowed_extra_profit"],
            init_params2["fee_gamma"],
            init_params2["adjustment_step"],
            init_params2["admin_fee"],
            init_params2["ma_time"],
            INITIAL_PRICES,
            name="TricryptoSwap",
        )
        token2.set_minter(swap.address)

    return swap


@pytest.fixture(scope="module")
def swap3_empty(owner, fee_receiver, init_params3, math3, coins, deployer):

    path = "contracts/CurveTricryptoOptimized.vy"

    with open(path, "r") as f:
        source = f.read()
        source = source.replace(
            "0x0000000000000000000000000000000000000000",
            math3.address,
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

    with boa.env.prank(deployer):
        swap = boa.loads(
            source,
            owner,
            fee_receiver,
            init_params3["A"],
            init_params3["gamma"],
            init_params3["mid_fee"],
            init_params3["out_fee"],
            init_params3["allowed_extra_profit"],
            init_params3["fee_gamma"],
            init_params3["adjustment_step"],
            init_params3["admin_fee"],
            init_params3["ma_time"],
            INITIAL_PRICES,
            name="TricryptoSwapOptimized",
        )
    return swap


@pytest.fixture(scope="module")
def views3(deployer, math3, swap3_empty):
    with boa.env.prank(deployer):
        return boa.load(
            "contracts/CurveCryptoViews3Optimized.vy",
            math3,
            swap3_empty,
            name="TricryptoViewsOptimized",
        )


@pytest.fixture(scope="module")
def swap2(swap2_empty, coins, user):
    quantities = [
        10**6 * 10**36 // p for p in [10**18] + INITIAL_PRICES
    ]  # $3M worth

    for coin, quantity in zip(coins, quantities):
        # mint coins for user:
        mint_for_testing(coin, user, quantity)
        assert coin.balanceOf(user) == quantity

        # approve crypto_swap to trade coin for user:
        with boa.env.prank(user):
            coin.approve(swap2_empty, 2**256 - 1)

    # Very first deposit
    with boa.env.prank(user):
        swap2_empty.add_liquidity(quantities, 0)

    return swap2_empty


@pytest.fixture(scope="module")
def swap3(swap3_empty, coins, user):

    quantities = [10**6 * 10**36 // p for p in [10**18] + INITIAL_PRICES]

    for coin, quantity in zip(coins, quantities):
        # mint coins for user:
        mint_for_testing(coin, user, quantity)
        assert coin.balanceOf(user) == quantity

        # approve crypto_swap to trade coin for user:
        with boa.env.prank(user):
            coin.approve(swap3_empty, 2**256 - 1)

    # Very first deposit
    with boa.env.prank(user):
        swap3_empty.add_liquidity(quantities, 0)

    return swap3_empty
