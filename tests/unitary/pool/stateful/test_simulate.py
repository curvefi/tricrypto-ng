from math import log

import boa
from boa.test import strategy
from hypothesis.stateful import invariant, rule, run_state_machine_as_test

from tests.unitary.pool.stateful.stateful_base import StatefulBase
from tests.utils import simulation_int_many as sim
from tests.utils.tokens import mint_for_testing

MAX_SAMPLES = 100
STEP_COUNT = 100


def approx(x1, x2, precision):
    return abs(log(x1 / x2)) <= precision


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
        A_gamma = [self.swap.A(), self.swap.gamma()]
        fee_params = self.swap.internal._unpack(
            self.swap._storage.packed_fee_params.get()
        )
        rebal_params = self.swap.internal._unpack(
            self.swap._storage.packed_rebalancing_params.get()
        )

        self.trader = sim.Trader(
            A_gamma[0],
            A_gamma[1],
            self.swap.D(),
            3,
            [10**18] + [self.swap.price_scale(i) for i in range(2)],
            mid_fee=fee_params[0] / 1e10,
            out_fee=fee_params[1] / 1e10,
            fee_gamma=fee_params[2],
            allowed_extra_profit=rebal_params[0],
            adjustment_step=rebal_params[1] / 1e18,
            ma_time=rebal_params[2],
        )
        for i in range(3):
            self.trader.curve.x[i] = self.swap.balances(i)

        # Adjust virtual prices
        self.trader.xcp_profit = self.swap.xcp_profit()
        self.trader.xcp_profit_real = self.swap._storage.virtual_price.get()
        self.trader.t = boa.env.vm.state.timestamp

        print("\n------------------- initialised!")
        print(
            "swap balances: ",
            [
                self.swap.balances(0) / 1e18,
                self.swap.balances(1) / 1e18,
                self.swap.balances(2) / 1e18,
            ],
        )
        print("swap xp: ", [k / 1e18 for k in self.swap.internal.xp()])
        self.step = 0

    @rule(
        exchange_amount_in=exchange_amount_in,
        exchange_i=exchange_i,
        exchange_j=exchange_j,
        user=user,
    )
    def exchange(self, exchange_amount_in, exchange_i, exchange_j, user):

        if exchange_i == exchange_j:
            return

        print(f"Step {self.step}: ")
        self.step += 1
        print("exchange amount in: ", exchange_amount_in / 10**18, " USD")
        print("exchange_i: ", exchange_i)
        print("exchange_j: ", exchange_j)
        print(
            "trader price oracle: ",
            [k / 1e18 for k in self.trader.price_oracle],
        )

        exchange_amount_in = (
            exchange_amount_in
            * 10**18
            // self.trader.price_oracle[exchange_i]
        )
        print("dx in: ", exchange_amount_in / 1e18)

        xp = self.swap.internal.xp()
        D = self.swap.D()
        print("swap xp before: ", [k / 1e18 for k in xp])
        print("swap xp_i/D before: ", [f / D for f in xp])
        print(
            "swap price scale before: ",
            [k / 1e18 for k in get_price_scale(self.swap)],
        )
        print(
            "swap price oracle before: ",
            [
                self.swap.price_oracle(0) / 1e18,
                self.swap.price_oracle(1) / 1e18,
            ],
        )

        dy_swap = super().exchange(
            exchange_amount_in, exchange_i, exchange_j, user
        )

        if not dy_swap:
            print("swap failed!")
            print()

        else:

            dy_trader = self.trader.buy(
                exchange_amount_in, exchange_i, exchange_j
            )

            # we calculate price from a small trade post swap
            # since this is similar to get_p (analytical price calc):
            prices = [
                10**16
                * 10**18
                // self.views.internal._get_dy_nofee(
                    0, 1, 10**16, self.swap
                )[0],
                10**16
                * 10**18
                // self.views.internal._get_dy_nofee(
                    0, 2, 10**16, self.swap
                )[0],
            ]

            print("dy swap: ", dy_swap / 10**18)
            print("dy trader: ", dy_trader / 10**18)
            print("swap price: ", prices)

            self.trader.tweak_price(
                boa.env.vm.state.timestamp, exchange_i, exchange_j, prices
            )

            # check if output value from exchange is similar
            assert abs(log(dy_swap / dy_trader)) < 1e-3

            xp = self.swap.internal.xp()
            D = self.swap.D()

            print("trader xp: ", [k / 1e18 for k in self.trader.curve.xp()])
            print("swap xp: ", [k / 1e18 for k in xp])
            print("swap xp_i/D: ", [f / D for f in xp])
            print(
                "trader curve price scale: ",
                [k / 1e18 for k in self.trader.curve.p[1:]],
            )
            print(
                "swap price scale: ",
                [k / 1e18 for k in get_price_scale(self.swap)],
            )
            print(
                "trader price oracle: ",
                [k / 1e18 for k in self.trader.price_oracle[1:]],
            )
            print(
                "swap price oracle: ",
                [
                    self.swap.price_oracle(0) / 1e18,
                    self.swap.price_oracle(1) / 1e18,
                ],
            )
            boa.env.time_travel(12)
            print(">>>>>>>>> time travelling by 12 seconds!")
            print()

    @invariant()
    def simulator(self):

        if self.trader.xcp_profit / 1e18 - 1 > 1e-8:

            assert (
                abs(self.trader.xcp_profit - self.swap.xcp_profit())
                / (self.trader.xcp_profit - 10**18)
                < 0.05
            )

        for i in range(2):
            try:
                price_scale = self.swap.price_scale(i)
                price_trader = self.trader.curve.p[i + 1]
                assert approx(price_scale, price_trader, 1e-3)
            except:  # noqa: E722
                print("---------- Error!")
                xp = self.swap.internal.xp()
                print("swap xp: ", [k / 1e18 for k in xp])
                D = self.swap.D()
                print("swap D: ", D / 1e18)
                xp_D = [f / D for f in xp]
                print("swap xp_i/D: ", xp_D)
                print(
                    "swap balances: ",
                    [
                        self.swap.balances(0) / 1e18,
                        self.swap.balances(1) / 1e18,
                        self.swap.balances(2) / 1e18,
                    ],
                )
                print("swap A_gamma: ", self.swap.A(), self.swap.gamma())

                if self.check_limits([0, 0, 0]):
                    assert False
                print("-------------------")


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
