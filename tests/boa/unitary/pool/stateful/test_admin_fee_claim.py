from math import log

from boa.test import strategy
from hypothesis.stateful import rule, run_state_machine_as_test

# from tests.boa.unitary.pool.stateful.stateful_base import StatefulBase
from tests.boa.unitary.pool.stateful.test_stateful import ProfitableState

MAX_SAMPLES = 20
STEP_COUNT = 100
NO_CHANGE = 2**256 - 1

# TODO: Test admin fee claims considering the various cases where it is disallowed.  # noqa: E501


def approx(x1, x2, precision):
    return abs(log(x1 / x2)) <= precision


class StatefulAdmin(ProfitableState):
    exchange_amount_in = strategy(
        "uint256", min_value=10**17, max_value=10**5 * 10**18
    )
    deposit_amounts = strategy(
        "uint256[3]", min_value=10**18, max_value=10**9 * 10**18
    )
    token_amount = strategy(
        "uint256", min_value=10**18, max_value=10**12 * 10**18
    )
    exchange_i = strategy("uint8", max_value=2)
    exchange_j = strategy("uint8", max_value=2)
    user = strategy("address")

    def setup(self):
        super().setup(user_id=1)

        packed_fee_params = self.swap._storage.packed_fee_params.get()
        unpacked_fee_params = self.swap.internal._unpack(packed_fee_params)
        self.mid_fee = unpacked_fee_params[0]
        self.out_fee = unpacked_fee_params[1]
        self.admin_fee = 5 * 10**9

    @rule(
        exchange_amount_in=exchange_amount_in,
        exchange_i=exchange_i,
        exchange_j=exchange_j,
        user=user,
    )
    def exchange(self, exchange_amount_in, exchange_i, exchange_j, user):

        if exchange_i > 0:
            exchange_amount_in_converted = (
                exchange_amount_in
                * 10**18
                // self.swap.price_oracle(exchange_i - 1)
            )
        else:
            exchange_amount_in_converted = exchange_amount_in

        super().exchange(
            exchange_amount_in_converted, exchange_i, exchange_j, user
        )

    @rule(deposit_amounts=deposit_amounts, user=user)
    def deposit(self, deposit_amounts, user):
        deposit_amounts[1:] = [deposit_amounts[0]] + [
            deposit_amounts[i] * 10**18 // self.swap.price_oracle(i - 1)
            for i in [1, 2]
        ]
        super().deposit(deposit_amounts, user)

    @rule(
        token_amount=token_amount,
        exchange_i=exchange_i,
        user=user,
    )
    def remove_liquidity_one_coin(self, token_amount, exchange_i, user):

        super().remove_liquidity_one_coin(
            token_amount, exchange_i, user, False
        )


def test_admin_fee(swap, views_contract, users, pool_coins, tricrypto_factory):
    from hypothesis import settings
    from hypothesis._settings import HealthCheck

    StatefulAdmin.TestCase.settings = settings(
        max_examples=MAX_SAMPLES,
        stateful_step_count=STEP_COUNT,
        suppress_health_check=HealthCheck.all(),
        deadline=None,
    )

    for k, v in locals().items():
        setattr(StatefulAdmin, k, v)

    run_state_machine_as_test(StatefulAdmin)
