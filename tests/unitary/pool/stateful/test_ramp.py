import boa
from boa.test import strategy
from hypothesis.stateful import invariant, rule, run_state_machine_as_test

from tests.unitary.pool.stateful.test_stateful import ProfitableState

MAX_SAMPLES = 20
MAX_COUNT = 100
MAX_D = 10**12 * 10**18  # $1T is hopefully a reasonable cap for tests
ALLOWED_DIFFERENCE = 0.001


class RampTest(ProfitableState):
    check_out_amount = strategy("bool")
    exchange_amount_in = strategy(
        "uint256", min_value=10**18, max_value=50000 * 10**18
    )
    token_amount = strategy(
        "uint256", min_value=10**18, max_value=10**12 * 10**18
    )
    deposit_amounts = strategy(
        "uint256[3]", min_value=10**18, max_value=10**9 * 10**18
    )
    exchange_i = strategy("uint8", max_value=2)
    exchange_j = strategy("uint8", max_value=2)
    user = strategy("address")

    def setup(self, user_id=0):
        super().setup(user_id)
        A_gamma = self.swap.A_gamma()
        new_A = A_gamma[0] * 2
        new_gamma = A_gamma[1] * 2

        block_time = boa.env.vm.state.timestamp
        with boa.env.prank(self.tricrypto_factory.admin()):
            self.swap.ramp_A_gamma(new_A, new_gamma, block_time + 14 * 86400)

    @rule(deposit_amounts=deposit_amounts, user=user)
    def deposit(self, deposit_amounts, user):
        deposit_amounts[1:] = [deposit_amounts[0]] + [
            deposit_amounts[i] * 10**18 // self.swap.price_oracle(i - 1)
            for i in [1, 2]
        ]
        super().deposit(deposit_amounts, user)

    @rule(
        exchange_amount_in=exchange_amount_in,
        exchange_i=exchange_i,
        exchange_j=exchange_j,
        user=user,
        check_out_amount=check_out_amount,
    )
    def exchange(
        self,
        exchange_amount_in,
        exchange_i,
        exchange_j,
        user,
        check_out_amount,
    ):
        if check_out_amount:
            self.swap.claim_admin_fees()
        if exchange_i > 0:
            exchange_amount_in = (
                exchange_amount_in
                * 10**18
                // self.swap.price_oracle(exchange_i - 1)
            )
            if exchange_amount_in < 1000:
                return

        super()._exchange(
            exchange_amount_in,
            exchange_i,
            exchange_j,
            user,
            ALLOWED_DIFFERENCE if check_out_amount else False,
        )

    @rule(
        token_amount=token_amount,
        exchange_i=exchange_i,
        user=user,
        check_out_amount=check_out_amount,
    )
    def remove_liquidity_one_coin(
        self, token_amount, exchange_i, user, check_out_amount
    ):
        if check_out_amount:
            self.swap.claim_admin_fees()
            super().remove_liquidity_one_coin(
                token_amount, exchange_i, user, ALLOWED_DIFFERENCE
            )
        else:
            super().remove_liquidity_one_coin(
                token_amount, exchange_i, user, False
            )

    @invariant()
    def virtual_price(self):
        # Invariant is not conserved here
        pass


def test_ramp(swap, views_contract, users, pool_coins, tricrypto_factory):
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
