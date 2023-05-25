import boa
import pytest
from boa.test import strategy
from hypothesis.stateful import rule, run_state_machine_as_test

from tests.boa.unitary.pool.stateful.test_stateful import ProfitableState

COINS = [("USDC", 6), ("WBTC", 8), ("WETH", 18)]
INITIAL_PRICES = [10**18, 17500 * 10**18, 1200 * 10**18]

MAX_SAMPLES = 20
MAX_COUNT = 20


# Fixtures
@pytest.fixture(scope="module", autouse=True)
def pool_coins(deployer, weth):
    with boa.env.prank(deployer):
        yield [
            boa.load("contracts/mocks/ERC20Mock.vy", name, name, decimals)
            for name, decimals in COINS[:2]
        ] + [weth]


@pytest.fixture(scope="module")
def swap(
    tricrypto_factory,
    amm_interface,
    pool_coins,
    params,
    deployer,
    weth,
):
    with boa.env.prank(deployer):
        swap = tricrypto_factory.deploy_pool(
            "Curve.fi USDC-BTC-ETH",
            "USDCBTCETH",
            [coin.address for coin in pool_coins],
            weth,
            0,  # <-------- 0th implementation index
            params["A"],
            params["gamma"],
            params["mid_fee"],
            params["out_fee"],
            params["allowed_extra_profit"],
            params["fee_gamma"],
            params["adjustment_step"],
            params["ma_time"],
            params["initial_prices"],
        )

    return amm_interface.at(swap)


class MultiPrecision(ProfitableState):
    exchange_amount_in = strategy(
        "uint256", min_value=10**17, max_value=10**5 * 10**18
    )
    exchange_i = strategy("uint8", max_value=2)
    exchange_j = strategy("uint8", max_value=2)
    user = strategy("address")

    @rule(
        exchange_amount_in=exchange_amount_in,
        exchange_i=exchange_i,
        exchange_j=exchange_j,
        user=user,
    )
    def exchange(self, exchange_amount_in, exchange_i, exchange_j, user):
        exchange_amount_in = exchange_amount_in // 10 ** (
            18 - self.decimals[exchange_i]
        )
        super().exchange(exchange_amount_in, exchange_i, exchange_j, user)


def test_multiprecision(
    swap, views_contract, users, pool_coins, tricrypto_factory
):
    from hypothesis import settings
    from hypothesis._settings import HealthCheck

    MultiPrecision.TestCase.settings = settings(
        max_examples=MAX_SAMPLES,
        stateful_step_count=MAX_COUNT,
        suppress_health_check=HealthCheck.all(),
        deadline=None,
    )

    for k, v in locals().items():
        setattr(MultiPrecision, k, v)

    run_state_machine_as_test(MultiPrecision)
