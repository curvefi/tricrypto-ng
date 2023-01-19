from math import log

import boa
from boa.test import strategy
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from tests.fixtures.pool import INITIAL_PRICES
from tests.utils.tokens import mint_for_testing


class StatefulBase(RuleBasedStateMachine):
    exchange_amount_in = strategy("uint256", max_value=10**9 * 10**18)
    exchange_i = strategy("uint8", max_value=2)
    exchange_j = strategy("uint8", max_value=2)
    sleep_time = strategy("uint256", max_value=86400 * 7)
    user = strategy("address")

    def __init__(self):

        super().__init__()

        self.accounts = self.users
        self.views = self.views_contract
        self.coins = self.pool_coins
        self.token = self.swap

        self.swap_admin = self.tricrypto_factory.admin()
        self.fee_receiver = self.tricrypto_factory.fee_receiver()

        self.decimals = [int(c.decimals()) for c in self.coins]
        self.initial_prices = INITIAL_PRICES
        self.initial_deposit = [
            10**4 * 10 ** (18 + d) // p
            for p, d in zip(self.initial_prices, self.decimals)
        ]  # $10k * 3
        self.user_balances = {u: [0] * 3 for u in self.accounts}
        self.balances = self.initial_deposit[:]
        self.xcp_profit = 10**18
        self.total_supply = 0

        for user in self.accounts:
            for coin in self.coins:
                with boa.env.prank(user):
                    coin.approve(self.swap, 2**256 - 1)

        self.setup()

    def setup(self, user_id=0):
        user = self.accounts[user_id]
        for coin, q in zip(self.coins, self.initial_deposit):
            mint_for_testing(coin, user, q)

        with boa.env.prank(user):
            self.swap.add_liquidity(self.initial_deposit, 0)

        assert self.token.totalSupply() > 0
        self.total_supply = self.token.balanceOf(user)

    def state_dump(self):
        amm_balances = []
        for i in range(len(self.coins)):
            amm_balances.append(self.swap.balances(i))

        price_oracle = [self.swap.price_oracle(0), self.swap.price_oracle(1)]
        price_scale = [self.swap.price_scale(0), self.swap.price_scale(1)]

        return {
            "balances": amm_balances,
            "price_oracle": price_oracle,
            "price_scale": price_scale,
            "fee": self.swap.fee(),
        }

    def get_coin_balance(self, user, coin):
        if coin.symbol() == "WETH":
            return boa.env.get_balance(user)
        return coin.balanceOf(user)

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
        prices = [10**18] + [self.swap.price_scale()]
        xp_0 = [self.swap.balances(i) for i in range(2)]
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
                    (min(_xp) * 10**18 // max(_xp) < 10**14)
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
            calc_amount = self.views.get_dy(
                exchange_i, exchange_j, exchange_amount_in, self.swap
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
        self.views.get_dy(
            exchange_j,
            exchange_i,
            10**16
            * 10 ** self.decimals[exchange_j]
            // ([10**18] + INITIAL_PRICES)[exchange_j],
            self.swap,
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
    def sleep(self, sleep_time):
        boa.env.time_travel(sleep_time)

    @invariant()
    def balances(self):
        balances = [self.swap.balances(i) for i in range(3)]
        eth_balance_amm = boa.env.get_balance(self.swap.address)
        balances_of = [c.balanceOf(self.swap) for c in self.coins]
        balances_of[2] = eth_balance_amm  # eth is set at i==2
        for i in range(3):
            assert self.balances[i] == balances[i]
            assert self.balances[i] == balances_of[i]

    @invariant()
    def lp_token_total_supply(self):
        assert self.total_supply == self.token.totalSupply()

    @invariant()
    def virtual_price(self):
        virtual_price = self.swap._storage.virtual_price.get()
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
