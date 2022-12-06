import boa
from boa.test import strategy
from hypothesis.stateful import (
    initialize,
    invariant,
    rule,
    run_state_machine_as_test,
)

from tests.unitary.tricrypto.stateful.test_stateful import ProfitableState
from tests.utils import mine

MAX_SAMPLES = 100
MAX_COUNT = 100
MAX_D = 10**12 * 10**18  # $1T is hopefully a reasonable cap for tests
ALLOWED_DIFFERENCE = 0.02


class RampTest(ProfitableState):
    future_gamma = strategy(
        "uint256",
        min_value=int(7e-5 * 1e18 / 9),
        max_value=int(7e-5 * 1e18 * 9),
    )
    future_A = strategy(
        "uint256",
        min_value=135 * 3**3 * 10000 // 9,
        max_value=3**3 * 10000 * 1000,
    )

    exchange_amount_in = strategy(
        "uint256", min_value=10**18, max_value=50000 * 10**18
    )
    token_amount = strategy(
        "uint256", min_value=10**18, max_value=10**12 * 10**18
    )
    exchange_i = strategy("uint8", max_value=2)
    exchange_j = strategy("uint8", max_value=2)
    user = strategy("address")

    @initialize(future_A=future_A, future_gamma=future_gamma)
    def initialize(self, future_A, future_gamma):
        with boa.env.prank(self.swap.owner()), mine():
            self.swap.ramp_A_gamma(
                future_A,
                future_gamma,
                boa.env.vm.state.timestamp + 14 * 86400,
            )

    @rule(
        exchange_amount_in=exchange_amount_in,
        exchange_i=exchange_i,
        exchange_j=exchange_j,
        user=user,
    )
    def exchange(self, exchange_amount_in, exchange_i, exchange_j, user):
        super()._exchange(
            exchange_amount_in, exchange_i, exchange_j, user, False
        )

    @rule(token_amount=token_amount, exchange_i=exchange_i, user=user)
    def remove_liquidity_one_coin(self, token_amount, exchange_i, user):
        super().remove_liquidity_one_coin(
            token_amount, exchange_i, user, False
        )

    @invariant()
    def virtual_price(self):
        # Invariant is not conserved here
        # so we need to override super().virtual_price()
        pass


def test_ramp(tricrypto_swap, tricrypto_lp_token, users, pool_coins):
    from hypothesis import settings
    from hypothesis._settings import HealthCheck

    RampTest.TestCase.settings = settings(
        max_examples=MAX_SAMPLES,
        stateful_step_count=MAX_COUNT,
        suppress_health_check=HealthCheck.all(),
        deadline=None,
    )

    for k, v in locals().items():
        setattr(RampTest, k, v)

    run_state_machine_as_test(RampTest)
