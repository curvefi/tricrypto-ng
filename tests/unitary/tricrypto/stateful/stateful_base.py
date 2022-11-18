from math import log

import boa
from boa.test import strategy
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from tests.fixtures.tricrypto import INITIAL_PRICES
from tests.utils import boa_sleep
from tests.utils.tokens import mint_for_testing

MAX_SAMPLES = 20
MAX_D = 10**12 * 10**18  # $1T is hopefully a reasonable cap for tests


class StatefulBase(RuleBasedStateMachine):
    exchange_amount_in = strategy("uint256", max_value=10**9 * 10**18)
    exchange_i = strategy("uint8", max_value=2)
    exchange_j = strategy("uint8", max_value=2)
    sleep_time = strategy("uint256", max_value=86400 * 7)
    user = strategy("address")

    def __init__(self):
        super().__init__()
        self.anchor = boa.env.anchor()
        self.anchor.__enter__()

        self.accounts = self.users
        self.swap = self.tricrypto_swap
        self.coins = self.pool_coins
        self.token = self.tricrypto_lp_token

        self.decimals = [int(c.decimals()) for c in self.coins]
        self.initial_deposit = [
            10**4 * 10 ** (18 + d) // p
            for p, d in zip([10**18] + INITIAL_PRICES, self.decimals)
        ]  # $10k * 3
        self.initial_prices = [10**18] + INITIAL_PRICES
        self.user_balances = {u: [0] * 3 for u in self.accounts}
        self.balances = self.initial_deposit[:]
        self.xcp_profit = 10**18
        self.total_supply = 0

        for user in self.accounts:
            for coin in self.coins:
                with boa.env.prank(user):
                    coin.approve(self.swap, 2**256 - 1)

        self.setup()

    def setup(self):
        user = self.accounts[0]
        for coin, q in zip(self.coins, self.initial_deposit):
            mint_for_testing(coin, user, q)

        with boa.env.prank(user):
            self.swap.add_liquidity(self.initial_deposit, 0)

        self.total_supply = self.token.balanceOf(user)

    def teardown(self):
        self.anchor.__exit__(None, None, None)

    def convert_amounts(self, amounts):
        prices = [10**18] + [self.swap.price_scale(i) for i in range(2)]
        return [
            p * a // 10 ** (36 - d)
            for p, a, d in zip(prices, amounts, self.decimals)
        ]

    def check_limits(self, amounts, D=True, y=True):
        """
        Should be good if within limits, but if outside - can be either
        """
        _D = self.swap.D()
        prices = [10**18] + [self.swap.price_scale(i) for i in range(2)]
        xp_0 = [self.swap.balances(i) for i in range(3)]
        xp = xp_0
        xp_0 = [
            x * p // 10**d for x, p, d in zip(xp_0, prices, self.decimals)
        ]
        xp = [
            (x + a) * p // 10**d
            for a, x, p, d in zip(amounts, xp, prices, self.decimals)
        ]

        if D:
            for _xp in [xp_0, xp]:
                if (
                    (min(_xp) * 10**18 // max(_xp) < 10**11)
                    or (max(_xp) < 10**9 * 10**18)
                    or (max(_xp) > 10**15 * 10**18)
                ):
                    return False

        if y:
            for _xp in [xp_0, xp]:
                if (
                    (_D < 10**17)
                    or (_D > 10**15 * 10**18)
                    or (min(_xp) * 10**18 // _D < 10**16)
                    or (max(_xp) * 10**18 // _D > 10**20)
                ):
                    return False

        return True

    @rule(
        exchange_amount_in=exchange_amount_in,
        exchange_i=exchange_i,
        exchange_j=exchange_j,
        user=user,
    )
    def exchange(self, exchange_amount_in, exchange_i, exchange_j, user):
        return self._exchange(exchange_amount_in, exchange_i, exchange_j, user)

    def _exchange(
        self,
        exchange_amount_in,
        exchange_i,
        exchange_j,
        user,
        check_out_amount=True,
    ):
        if exchange_i == exchange_j:
            return False
        try:
            calc_amount = self.swap.get_dy(
                exchange_i, exchange_j, exchange_amount_in
            )
        except Exception:
            _amounts = [0] * 3
            _amounts[exchange_i] = exchange_amount_in
            if self.check_limits(_amounts):
                raise
            return False

        mint_for_testing(self.coins[exchange_i], user, exchange_amount_in)

        d_balance_i = self.coins[exchange_i].balanceOf(user)
        d_balance_j = self.coins[exchange_j].balanceOf(user)
        try:
            with boa.env.prank(user):
                self.coins[exchange_i].approve(self.swap, 2**256 - 1)
                self.swap.exchange(
                    exchange_i, exchange_j, exchange_amount_in, 0
                )
        except Exception:
            # Small amounts may fail with rounding errors
            if (
                calc_amount > 100
                and exchange_amount_in > 100
                and calc_amount / self.swap.balances(exchange_j) > 1e-13
                and exchange_amount_in / self.swap.balances(exchange_i) > 1e-13
            ):
                raise
            return False

        # This is to check that we didn't end up in a borked state after
        # an exchange succeeded
        self.swap.get_dy(
            exchange_j,
            exchange_i,
            10**16
            * 10 ** self.decimals[exchange_j]
            // ([10**18] + INITIAL_PRICES)[exchange_j],
        )

        d_balance_i -= self.coins[exchange_i].balanceOf(user)
        d_balance_j -= self.coins[exchange_j].balanceOf(user)

        assert d_balance_i == exchange_amount_in
        if check_out_amount:
            if check_out_amount is True:
                assert (
                    -d_balance_j == calc_amount
                ), f"{-d_balance_j} vs {calc_amount}"
            else:
                assert abs(d_balance_j + calc_amount) < max(
                    check_out_amount * calc_amount, 3
                ), f"{-d_balance_j} vs {calc_amount}"

        self.balances[exchange_i] += d_balance_i
        self.balances[exchange_j] += d_balance_j

        return True

    @rule(sleep_time=sleep_time)
    def rule_sleep(self, sleep_time):
        boa_sleep(sleep_time)

    @invariant()
    def balances(self):
        balances = [self.swap.balances(i) for i in range(3)]
        balances_of = [c.balanceOf(self.swap) for c in self.coins]
        for i in range(3):
            assert self.balances[i] == balances[i]
            assert self.balances[i] == balances_of[i]

    @invariant()
    def total_supply(self):
        assert self.total_supply == self.token.totalSupply()

    @invariant()
    def virtual_price(self):
        virtual_price = self.swap.virtual_price()
        xcp_profit = self.swap.xcp_profit()
        get_virtual_price = self.swap.get_virtual_price()

        assert xcp_profit >= 10**18 - 10
        assert virtual_price >= 10**18 - 10
        assert get_virtual_price >= 10**18 - 10

        assert (
            xcp_profit - self.xcp_profit > -3
        ), f"{xcp_profit} vs {self.xcp_profit}"
        assert (virtual_price - 10**18) * 2 - (
            xcp_profit - 10**18
        ) >= -5, f"vprice={virtual_price}, xcp_profit={xcp_profit}"
        assert abs(log(virtual_price / get_virtual_price)) < 1e-10

        self.xcp_profit = xcp_profit
