import boa
from boa.test import strategy
from hypothesis.stateful import rule, run_state_machine_as_test

from tests.boa.unitary.pool.stateful.stateful_base import StatefulBase
from tests.boa.utils import approx
from tests.boa.utils.tokens import mint_for_testing

MAX_SAMPLES = 100
STEP_COUNT = 100


class StatefulGas(StatefulBase):
    exchange_amount_in = strategy(
        "uint256", min_value=10 * 10**18, max_value=100 * 10**18
    )
    deposit_amount = strategy(
        "uint256", min_value=10 * 10**18, max_value=100 * 10**18
    )
    token_fraction = strategy(
        "uint256", min_value=10**14, max_value=5 * 10**16
    )
    sleep_time = strategy("uint256", max_value=100)
    update_D = strategy("bool")
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
        if exchange_i > 0:
            exchange_amount_in = (
                exchange_amount_in
                * 10**18
                // self.swap.price_oracle(exchange_i - 1)
            )
        super().exchange(exchange_amount_in, exchange_i, exchange_j, user)

    @rule(deposit_amount=deposit_amount, exchange_i=exchange_i, user=user)
    def deposit(self, deposit_amount, exchange_i, user):

        amounts = [0] * 3
        if exchange_i > 0:

            amounts[exchange_i] = (
                deposit_amount
                * 10**18
                // self.swap.price_oracle(exchange_i - 1)
            )

        else:

            amounts[exchange_i] = deposit_amount

        mint_for_testing(self.coins[exchange_i], user, deposit_amount)

        with boa.env.prank(user):
            for coin in self.coins:
                coin.approve(self.swap, 2**256 - 1)

        try:

            tokens = self.token.balanceOf(user)

            with boa.env.prank(user), self.upkeep_on_claim():
                self.swap.add_liquidity(amounts, 0)

            tokens = self.token.balanceOf(user) - tokens
            self.total_supply += tokens

            for i in range(3):
                self.balances[i] += amounts[i]

        except Exception:

            if self.check_limits(amounts):
                raise

    @rule(
        token_fraction=token_fraction,
        exchange_i=exchange_i,
        user=user,
        update_D=update_D,
    )
    def remove_liquidity_one_coin(
        self, token_fraction, exchange_i, user, update_D
    ):

        token_amount = token_fraction * self.total_supply // 10**18
        d_token = self.token.balanceOf(user)
        if token_amount == 0 or token_amount > d_token:
            return

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

        try:

            with boa.env.prank(user), self.upkeep_on_claim():
                d_balance = self.swap.remove_liquidity_one_coin(
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
        d_token = d_token - self.token.balanceOf(user)

        if update_D:
            assert approx(
                calc_out_amount, d_balance, 1e-5
            ), f"{calc_out_amount} vs {d_balance} for {token_amount}"

        self.balances[exchange_i] -= d_balance
        self.total_supply -= d_token

        # Virtual price resets if everything is withdrawn
        if self.total_supply == 0:
            self.virtual_price = 10**18


def test_gas(swap, views_contract, users, pool_coins, tricrypto_factory):
    from hypothesis import settings
    from hypothesis._settings import HealthCheck

    StatefulGas.TestCase.settings = settings(
        max_examples=MAX_SAMPLES,
        stateful_step_count=STEP_COUNT,
        suppress_health_check=HealthCheck.all(),
        deadline=None,
    )

    for k, v in locals().items():
        setattr(StatefulGas, k, v)

    run_state_machine_as_test(StatefulGas)
