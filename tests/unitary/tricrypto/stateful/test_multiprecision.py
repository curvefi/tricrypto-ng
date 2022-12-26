import boa
import pytest
from boa.test import strategy
from hypothesis.stateful import rule, run_state_machine_as_test

from tests.conftest import _compiled_swap, _crypto_swap
from tests.unitary.tricrypto.stateful.test_stateful import ProfitableState

COINS = [("USDC", 6), ("WBTC", 8), ("WETH", 18)]
INITIAL_PRICES = [17500 * 10**18, 1200 * 10**18]

MAX_SAMPLES = 100
MAX_COUNT = 20


# Fixtures
@pytest.fixture(scope="module", autouse=True)
def pool_coins(deployer, weth):
    with boa.env.prank(deployer):
        yield [
            boa.load("contracts/mocks/ERC20Mock.vy", name, name, decimals)
            for name, decimals in COINS[:2]
        ] + [weth]


@pytest.fixture(scope="module", autouse=True)
def tricrypto_lp_token_init(deployer):
    with boa.env.prank(deployer):
        yield boa.load(
            "contracts/old/CurveTokenV4.vy",
            "Curve USD-BTC-ETH",
            "crvUSDBTCETH",
        )


@pytest.fixture(scope="module", autouse=True)
def compiled_swap(
    tricrypto_math,
    tricrypto_lp_token_init,
    tricrypto_views,
    pool_coins,
    optimized,
):

    return _compiled_swap(
        pool_coins,
        tricrypto_math,
        tricrypto_lp_token_init,
        tricrypto_views,
        optimized,
    )


@pytest.fixture(scope="module", autouse=True)
def tricrypto_swap(
    compiled_swap,
    tricrypto_lp_token_init,
    owner,
    fee_receiver,
    tricrypto_pool_init_params,
    deployer,
    optimized,
):
    return _crypto_swap(
        compiled_swap,
        tricrypto_lp_token_init,
        owner,
        fee_receiver,
        tricrypto_pool_init_params,
        deployer,
        optimized,
    )


@pytest.fixture(scope="module", autouse=True)
def tricrypto_lp_token(tricrypto_lp_token_init, tricrypto_swap, optimized):
    if optimized:
        return tricrypto_swap
    return tricrypto_lp_token_init


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
    tricrypto_swap,
    tricrypto_lp_token,
    tricrypto_views,
    users,
    pool_coins,
    optimized,
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
