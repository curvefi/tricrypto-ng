import copy

import boa


def _apply_new_params(swap, params):
    swap.apply_new_parameters(
        params["mid_fee"],
        params["out_fee"],
        params["fee_gamma"],
        params["allowed_extra_profit"],
        params["adjustment_step"],
        params["ma_time"],
        params["xcp_ma_time"],
    )


def test_commit_accept_mid_fee(swap, factory_admin, params):

    p = copy.deepcopy(params)
    p["mid_fee"] = p["mid_fee"] + 1
    with boa.env.prank(factory_admin):
        _apply_new_params(swap, p)

    mid_fee = swap.internal._unpack(swap._storage.packed_fee_params.get())[0]
    assert mid_fee == p["mid_fee"]


def test_commit_accept_out_fee(swap, factory_admin, params):

    p = copy.deepcopy(params)
    p["out_fee"] = p["out_fee"] + 1
    with boa.env.prank(factory_admin):
        _apply_new_params(swap, p)

    out_fee = swap.internal._unpack(swap._storage.packed_fee_params.get())[1]
    assert out_fee == p["out_fee"]


def test_commit_accept_fee_gamma(swap, factory_admin, params):

    p = copy.deepcopy(params)
    p["fee_gamma"] = 10**17
    with boa.env.prank(factory_admin):
        _apply_new_params(swap, p)

    fee_gamma = swap.internal._unpack(swap._storage.packed_fee_params.get())[2]
    assert fee_gamma == p["fee_gamma"]


def test_commit_accept_fee_params(swap, factory_admin, params):

    p = copy.deepcopy(params)
    p["mid_fee"] += 1
    p["out_fee"] += 1
    p["fee_gamma"] = 10**17

    with boa.env.prank(factory_admin):
        _apply_new_params(swap, p)

    fee_params = swap.internal._unpack(swap._storage.packed_fee_params.get())
    assert fee_params[0] == p["mid_fee"]
    assert fee_params[1] == p["out_fee"]
    assert fee_params[2] == p["fee_gamma"]


def test_commit_accept_allowed_extra_profit(swap, factory_admin, params):

    p = copy.deepcopy(params)
    p["allowed_extra_profit"] = 10**17
    with boa.env.prank(factory_admin):
        _apply_new_params(swap, p)

    allowed_extra_profit = swap.internal._unpack(
        swap._storage.packed_rebalancing_params.get()
    )[0]
    assert allowed_extra_profit == p["allowed_extra_profit"]


def test_commit_accept_adjustment_step(swap, factory_admin, params):

    p = copy.deepcopy(params)
    p["adjustment_step"] = 10**17
    with boa.env.prank(factory_admin):
        _apply_new_params(swap, p)

    adjustment_step = swap.internal._unpack(
        swap._storage.packed_rebalancing_params.get()
    )[1]
    assert adjustment_step == p["adjustment_step"]


def test_commit_accept_ma_time(swap, factory_admin, params):

    p = copy.deepcopy(params)
    p["ma_time"] = 872
    with boa.env.prank(factory_admin):
        _apply_new_params(swap, p)

    ma_time = swap.internal._unpack(
        swap._storage.packed_rebalancing_params.get()
    )[2]
    assert ma_time == p["ma_time"]


def test_commit_accept_xcp_ma_time(swap, factory_admin, params):

    p = copy.deepcopy(params)
    p["xcp_ma_time"] = 872541
    with boa.env.prank(factory_admin):
        _apply_new_params(swap, p)

    assert swap.xcp_ma_time() == p["xcp_ma_time"]


def test_commit_accept_rebalancing_params(swap, factory_admin, params):

    p = copy.deepcopy(params)
    p["allowed_extra_profit"] = 10**17
    p["adjustment_step"] = 10**17
    p["ma_time"] = 1000

    with boa.env.prank(factory_admin):
        _apply_new_params(swap, p)

    rebalancing_params = swap.internal._unpack(
        swap._storage.packed_rebalancing_params.get()
    )
    assert rebalancing_params[0] == p["allowed_extra_profit"]
    assert rebalancing_params[1] == p["adjustment_step"]
    assert rebalancing_params[2] == p["ma_time"]
