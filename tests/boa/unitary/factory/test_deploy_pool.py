import boa
import pytest


@pytest.fixture(scope="module")
def empty_factory(deployer, fee_receiver, owner, weth):

    with boa.env.prank(deployer):
        factory = boa.load(
            "contracts/main/CurveTricryptoFactory.vy",
            fee_receiver,
            owner,
        )

    return factory


def test_check_packed_params_on_deployment(swap, params, coins):

    # check packed precisions
    unpacked_precisions = swap.precisions()
    for i in range(len(coins)):
        assert unpacked_precisions[i] == 10 ** (18 - coins[i].decimals())

    # check packed fees
    unpacked_fees = swap.internal._unpack_3(
        swap._storage.packed_fee_params.get()
    )
    assert params["mid_fee"] == unpacked_fees[0]
    assert params["out_fee"] == unpacked_fees[1]
    assert params["fee_gamma"] == unpacked_fees[2]

    # check packed rebalancing params
    unpacked_rebalancing_params = swap.internal._unpack_3(
        swap._storage.packed_rebalancing_params.get()
    )
    assert params["allowed_extra_profit"] == unpacked_rebalancing_params[0]
    assert params["adjustment_step"] == unpacked_rebalancing_params[1]
    assert params["ma_time"] == unpacked_rebalancing_params[2]

    # check packed A_gamma
    A = swap.A()
    gamma = swap.gamma()
    assert params["A"] == A
    assert params["gamma"] == gamma

    # check packed_prices
    price_oracle = [swap.price_oracle(i) for i in range(2)]
    price_scale = [swap.price_scale(i) for i in range(2)]
    last_prices = [swap.last_prices(i) for i in range(2)]

    for price in [price_oracle, price_scale, last_prices]:
        for i in range(2):
            assert price[i] == params["initial_prices"][i]


def test_check_pool_data_on_deployment(swap, tricrypto_factory, coins):

    for i, coin_a in enumerate(coins):
        for j, coin_b in enumerate(coins):

            if coin_a == coin_b:
                continue

            assert (
                tricrypto_factory.find_pool_for_coins(coin_a, coin_b).lower()
                == swap.address.lower()
            )

            tricrypto_factory.get_coin_indices(
                swap.address, coin_a, coin_b
            ) == (i, j)

    pool_coins = tricrypto_factory.get_coins(swap.address)
    coins_lower = [coin.address.lower() for coin in coins]
    for i in range(len(pool_coins)):
        assert pool_coins[i].lower() == coins_lower[i]

    pool_decimals = list(tricrypto_factory.get_decimals(swap.address))
    assert pool_decimals == [coin.decimals() for coin in coins]


def test_revert_deploy_without_implementations(
    empty_factory,
    coins,
    params,
    deployer,
    weth,
):
    with boa.env.prank(deployer):
        with boa.reverts("Pool implementation not set"):
            empty_factory.deploy_pool(
                "Curve.fi USDC-BTC-ETH",
                "USDCBTCETH",
                [coin.address for coin in coins],
                weth,
                0,
                params["A"],
                params["gamma"],
                params["mid_fee"],
                params["out_fee"],
                params["fee_gamma"],
                params["allowed_extra_profit"],
                params["adjustment_step"],
                params["ma_time"],  # <--- no admin_fee needed
                params["initial_prices"],
            )
