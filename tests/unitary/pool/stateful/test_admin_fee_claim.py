from math import log

import boa
from boa.test import strategy
from hypothesis.stateful import rule, run_state_machine_as_test

from tests.unitary.pool.stateful.stateful_base import StatefulBase

MAX_SAMPLES = 100
STEP_COUNT = 200
NO_CHANGE = 2**256 - 1


def approx(x1, x2, precision):
    return abs(log(x1 / x2)) <= precision


class StatefulAdmin(StatefulBase):
    exchange_amount_in = strategy(
        "uint256", min_value=10**17, max_value=10**5 * 10**18
    )
    exchange_i = strategy("uint8", max_value=2)
    exchange_j = strategy("uint8", max_value=2)
    user = strategy("address")

    def setup(self):
        super().setup(user_id=1)
        with boa.env.prank(self.swap_admin):
            self.swap.commit_new_parameters(
                NO_CHANGE,
                NO_CHANGE,
                5 * 10**9,  # admin fee
                NO_CHANGE,
                NO_CHANGE,
                NO_CHANGE,
                NO_CHANGE,
            )

            boa.env.time_travel(seconds=3 * 86400 + 1)
            self.swap.apply_new_parameters()

        assert self.swap.admin_fee() == 5 * 10**9
        self.mid_fee = self.swap.mid_fee()
        self.out_fee = self.swap.out_fee()
        self.admin_fee = 5 * 10**9

    @rule(
        exchange_amount_in=exchange_amount_in,
        exchange_i=exchange_i,
        exchange_j=exchange_j,
        user=user,
    )
    def exchange(self, exchange_amount_in, exchange_i, exchange_j, user):

        admin_balance = self.token.balanceOf(self.swap.admin_fee_receiver())

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

        admin_balance = (
            self.token.balanceOf(self.swap.admin_fee_receiver())
            - admin_balance
        )

        self.total_supply += admin_balance

    @rule()
    def claim_admin_fees(self):
        balance = self.token.balanceOf(self.swap.admin_fee_receiver())

        self.swap.claim_admin_fees()
        admin_balance = self.token.balanceOf(self.swap.admin_fee_receiver())
        balance = admin_balance - balance
        self.total_supply += balance

        if balance > 0:
            self.xcp_profit = self.swap.xcp_profit()
            measured_profit = admin_balance / self.total_supply
            try:
                assert approx(
                    measured_profit, log(self.xcp_profit / 1e18) / 2, 0.1
                )
            except AssertionError:
                balances = [self.swap.balances(i) for i in range(3)]
                if self.check_limits(balances):
                    raise


def test_admin(
    tricrypto_swap,
    tricrypto_lp_token,
    tricrypto_views,
    users,
    pool_coins,
    optimized,
):
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
