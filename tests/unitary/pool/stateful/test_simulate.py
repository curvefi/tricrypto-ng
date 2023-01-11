from math import log

import boa
from boa.test import strategy
from hypothesis.stateful import invariant, rule, run_state_machine_as_test

from tests.unitary.pool.stateful.stateful_base import StatefulBase
from tests.utils import simulation_int_many as sim
from tests.utils.tokens import mint_for_testing

MAX_SAMPLES = 100
STEP_COUNT = 200


def get_price_scale(swap):
    return [swap.price_scale(0), swap.price_scale(1)]


class StatefulSimulation(StatefulBase):
    exchange_amount_in = strategy(
        "uint256", min_value=10**17, max_value=10**5 * 10**18
    )
    exchange_i = strategy("uint8", max_value=2)
    exchange_j = strategy("uint8", max_value=2)
    user = strategy("address")

    def setup(self, user_id=0):

        super().setup()

        for u in self.accounts[1:]:
            for coin, q in zip(self.coins, self.initial_deposit):
                mint_for_testing(coin, u, q)
            for i in range(3):
                self.balances[i] += self.initial_deposit[i]
            with boa.env.prank(u):
                self.swap.add_liquidity(self.initial_deposit, 0)
            self.total_supply += self.token.balanceOf(u)

        self.virtual_price = self.swap.get_virtual_price()
        A_gamma = self.swap.A_gamma()
        fee_params = self.swap.internal._unpack(
            self.swap._storage.packed_fee_params.get()
        )
        self.trader = sim.Trader(
            A_gamma[0],
            A_gamma[1],
            self.swap.D(),
            3,
            [10**18] + [self.swap.price_scale(i) for i in range(2)],
            fee_params[0] / 1e10,
            fee_params[1] / 1e10,
            self.swap.allowed_extra_profit(),
            fee_params[2],
            self.swap.adjustment_step() / 1e18,
            self.swap.ma_time(),
        )
        for i in range(3):
            self.trader.curve.x[i] = self.swap.balances(i)

        # Adjust virtual prices
        self.trader.xcp_profit = self.swap.xcp_profit()
        self.trader.xcp_profit_real = self.swap._storage.virtual_price.get()
        self.trader.t = boa.env.vm.state.timestamp

    @rule(
        exchange_amount_in=exchange_amount_in,
        exchange_i=exchange_i,
        exchange_j=exchange_j,
        user=user,
    )
    def exchange(self, exchange_amount_in, exchange_i, exchange_j, user):
        exchange_amount_in = (
            exchange_amount_in
            * 10**18
            // self.trader.price_oracle[exchange_i]
        )

        price_scale = get_price_scale(self.swap)
        trader_price_scale = self.trader.curve.p

        if super().exchange(exchange_amount_in, exchange_i, exchange_j, user):
            dy = self.trader.buy(exchange_amount_in, exchange_i, exchange_j)
            price = exchange_amount_in * 10**18 // dy
            self.trader.tweak_price(
                boa.env.vm.state.timestamp, exchange_i, exchange_j, price
            )

            # ensure that if trader tweaks price, so does the amm:
            if self.trader.curve.p != trader_price_scale:
                assert get_price_scale(self.swap) != price_scale

    @invariant()
    def simulator(self):
        if self.trader.xcp_profit / 1e18 - 1 > 1e-8:
            assert (
                abs(self.trader.xcp_profit - self.swap.xcp_profit())
                / (self.trader.xcp_profit - 10**18)
                < 0.05
            )
        precision = 0.001
        for i in range(2):
            diff = abs(
                log(self.trader.curve.p[i + 1] / self.swap.price_scale(i))
            )
            balances = [self.swap.balances(i) for i in range(3)]
            if not diff <= precision and self.check_limits(balances):
                raise


def test_sim(swap, views_contract, users, pool_coins, tricrypto_factory):
    from hypothesis import settings
    from hypothesis._settings import HealthCheck

    StatefulSimulation.TestCase.settings = settings(
        max_examples=MAX_SAMPLES,
        stateful_step_count=STEP_COUNT,
        suppress_health_check=HealthCheck.all(),
        deadline=None,
    )

    for k, v in locals().items():
        setattr(StatefulSimulation, k, v)

    run_state_machine_as_test(StatefulSimulation)
