import boa
from boa.test import strategy
from hypothesis.stateful import rule, run_state_machine_as_test

from tests.conftest import INITIAL_PRICES
from tests.unitary.tricrypto.stateful.stateful_base import StatefulBase
from tests.utils.tokens import mint_for_testing

MAX_SAMPLES = 100
MAX_COUNT = 20
MAX_D = 10**12 * 10**18  # $1T is hopefully a reasonable cap for tests


class ProfitableState(StatefulBase):
    """
    Test that profit goes up
    """

    deposit_amounts = strategy(
        "uint256[3]", min_value=0, max_value=10**9 * 10**18
    )
    token_amount = strategy("uint256", max_value=10**12 * 10**18)
    check_out_amount = strategy("bool")
    user = strategy("address")
    exchange_i = strategy("uint8", max_value=2)

    @rule(deposit_amounts=deposit_amounts, user=user)
    def deposit(self, deposit_amounts, user):
        if self.swap.D() > MAX_D:
            return

        amounts = self.convert_amounts(deposit_amounts)
        new_balances = [x + y for x, y in zip(self.balances, amounts)]

        for coin, q in zip(self.coins, amounts):
            mint_for_testing(coin, user, q)

        try:
            tokens = self.token.balanceOf(user)
            with boa.env.prank(user):
                self.swap.add_liquidity(amounts, 0)
            tokens = self.token.balanceOf(user) - tokens
            self.total_supply += tokens
            self.balances = new_balances
        except Exception:
            if self.check_limits(amounts):
                raise
            else:
                return

        # This is to check that we didn't end up in a borked state after
        # an exchange succeeded
        try:
            if not self.optimized:
                self.swap.get_dy(0, 1, 10 ** (self.decimals[0] - 2))
            else:
                self.views.get_dy(0, 1, 10 ** (self.decimals[0] - 2))
        except Exception:
            if not self.optimized:
                self.swap.get_dy(
                    1,
                    0,
                    10**16
                    * 10 ** self.decimals[1]
                    // self.swap.price_scale(0),
                )
            else:
                self.views.get_dy(
                    1,
                    0,
                    10**16
                    * 10 ** self.decimals[1]
                    // self.swap.price_scale(0),
                )
        try:
            if not self.optimized:
                self.swap.get_dy(0, 2, 10 ** (self.decimals[0] - 2))
            else:
                self.views.get_dy(0, 2, 10 ** (self.decimals[0] - 2))
        except Exception:
            if not self.optimized:
                self.swap.get_dy(
                    2,
                    0,
                    10**16
                    * 10 ** self.decimals[2]
                    // self.swap.price_scale(1),
                )
            else:
                self.views.get_dy(
                    2,
                    0,
                    10**16
                    * 10 ** self.decimals[2]
                    // self.swap.price_scale(1),
                )

    @rule(token_amount=token_amount, user=user)
    def remove_liquidity(self, token_amount, user):
        if self.token.balanceOf(user) < token_amount or token_amount == 0:
            with boa.reverts(), boa.env.prank(user):
                self.swap.remove_liquidity(token_amount, [0] * 3)
        else:
            amounts = [c.balanceOf(user) for c in self.coins]
            tokens = self.token.balanceOf(user)
            with boa.env.prank(user):
                self.swap.remove_liquidity(token_amount, [0] * 3)
            tokens -= self.token.balanceOf(user)
            self.total_supply -= tokens
            amounts = [
                (c.balanceOf(user) - a) for c, a in zip(self.coins, amounts)
            ]
            self.balances = [b - a for a, b in zip(amounts, self.balances)]

            # Virtual price resets if everything is withdrawn
            if self.total_supply == 0:
                self.virtual_price = 10**18

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

        try:
            calc_out_amount = self.swap.calc_withdraw_one_coin(
                token_amount, exchange_i
            )
        except Exception:
            if self.check_limits([0] * 3) and not (
                token_amount > self.total_supply
            ):
                raise
            return

        d_token = self.token.balanceOf(user)
        if d_token < token_amount:
            with boa.reverts(), boa.env.prank(user):
                self.swap.remove_liquidity_one_coin(
                    token_amount, exchange_i, 0
                )
            return

        d_balance = self.coins[exchange_i].balanceOf(user)
        try:
            with boa.env.prank(user):
                self.swap.remove_liquidity_one_coin(
                    token_amount, exchange_i, 0
                )
        except Exception:
            # Small amounts may fail with rounding errors
            if (
                calc_out_amount > 100
                and token_amount / self.total_supply > 1e-10
                and calc_out_amount / self.swap.balances(exchange_i) > 1e-10
            ):
                raise
            return

        # This is to check that we didn't end up in a borked state after
        # an exchange succeeded
        _deposit = [0] * 3
        _deposit[exchange_i] = (
            10**16
            * 10 ** self.decimals[exchange_i]
            // ([10**18] + INITIAL_PRICES)[exchange_i]
        )
        self.views.calc_token_amount(_deposit, True)

        d_balance = self.coins[exchange_i].balanceOf(user) - d_balance
        d_token = d_token - self.token.balanceOf(user)

        if check_out_amount:
            if check_out_amount is True:
                assert (
                    calc_out_amount == d_balance
                ), f"{calc_out_amount} vs {d_balance} for {token_amount}"
            else:
                assert abs(calc_out_amount - d_balance) <= max(
                    check_out_amount * calc_out_amount, 5
                ), f"{calc_out_amount} vs {d_balance} for {token_amount}"

        self.balances[exchange_i] -= d_balance
        self.total_supply -= d_token

        # Virtual price resets if everything is withdrawn
        if self.total_supply == 0:
            self.virtual_price = 10**18


def test_numba_go_up(
    tricrypto_swap,
    tricrypto_lp_token,
    tricrypto_views,
    users,
    pool_coins,
    optimized,
):
    from hypothesis import settings
    from hypothesis._settings import HealthCheck

    ProfitableState.TestCase.settings = settings(
        max_examples=MAX_SAMPLES,
        stateful_step_count=MAX_COUNT,
        suppress_health_check=HealthCheck.all(),
        deadline=None,
    )

    for k, v in locals().items():
        setattr(ProfitableState, k, v)

    run_state_machine_as_test(ProfitableState)
