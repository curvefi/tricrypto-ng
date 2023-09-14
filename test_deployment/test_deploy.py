import pytest

from scripts.deployment_utils import (
    get_deposit_amounts,
    get_tricrypto_usdc_params,
)


class TestDeploy:
    PARAMS = get_tricrypto_usdc_params()

    @pytest.fixture(scope="function")
    def tokens_to_add(self, deploy):
        return get_deposit_amounts(
            500, self.PARAMS["initial_prices"], deploy[1]
        )

    def test_add_liquidity(
        self, admin, deploy, admin_mint_tokens, approve_admin, tokens_to_add
    ):
        pool = deploy[0]
        tx = pool.add_liquidity(tokens_to_add, 0, False, sender=admin)
        d_tokens = tx.return_value
        assert pool.balanceOf(admin) == pool.totalSupply() == d_tokens

    @pytest.mark.parametrize(("i", "j"), ((0, 1), (0, 2), (1, 2)))
    def test_exchange(
        self,
        admin,
        deploy,
        admin_mint_tokens,
        approve_admin,
        tokens_to_add,
        i,
        j,
    ):
        pool = deploy[0]
        pool.add_liquidity(tokens_to_add, 0, False, sender=admin)

        if i == 0:
            amount = 100 * 10 * 6
        else:
            amount = 1 * 10**6

        tx = pool.exchange_underlying(
            i,
            j,
            amount,
            0,
            sender=admin,
        )
        dy_eth = tx.events.filter(pool.TokenExchange)[
            0
        ].tokens_bought  # return_value is broken in ape somehow
        assert dy_eth > 0

    @pytest.mark.parametrize("i", (0, 1, 2))
    def test_remove_liquidity_one(
        self, admin, deploy, admin_mint_tokens, approve_admin, tokens_to_add, i
    ):
        pool = deploy[0]
        pool.add_liquidity(tokens_to_add, 0, False, sender=admin)

        bal = pool.balanceOf(admin)
        coin_contract = deploy[1][i]
        coin_balance = coin_contract.balanceOf(admin)

        tx = pool.remove_liquidity_one_coin(
            bal // 2,
            i,
            0,
            False,
            sender=admin,
        )  # noqa: E501

        dy_coin = tx.events.filter(pool.RemoveLiquidityOne)[0].coin_amount
        assert dy_coin > 0
        assert coin_contract.balanceOf(admin) == coin_balance + dy_coin
