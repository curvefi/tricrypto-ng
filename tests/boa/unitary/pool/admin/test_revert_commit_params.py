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


def test_commit_incorrect_fee_params(swap, factory_admin, params):

    p = copy.deepcopy(params)
    p["mid_fee"] = p["out_fee"] + 1
    with boa.env.prank(factory_admin):
        with boa.reverts("mid-fee is too high"):
            _apply_new_params(swap, p)

        p["out_fee"] = 0
        with boa.reverts("fee is out of range"):
            _apply_new_params(swap, p)

        # too large out_fee revert to old out_fee:
        p["mid_fee"] = params["mid_fee"]
        p["out_fee"] = 10**10 + 1  # <-- MAX_FEE
        _apply_new_params(swap, p)
        logs = swap.get_logs()[0]
        assert logs.args[1] == params["out_fee"]


def test_commit_incorrect_fee_gamma(swap, factory_admin, params):

    p = copy.deepcopy(params)
    p["fee_gamma"] = 0

    with boa.env.prank(factory_admin):

        with boa.reverts("fee_gamma out of range [1 .. 10**18]"):
            _apply_new_params(swap, p)

        p["fee_gamma"] = 10**18 + 1
        _apply_new_params(swap, p)

    # it will not change fee_gamma as it is above 10**18
    assert swap.get_logs()[0].args[2] == params["fee_gamma"]


def test_commit_rebalancing_params(swap, factory_admin, params):

    p = copy.deepcopy(params)
    p["allowed_extra_profit"] = 10**18 + 1
    p["adjustment_step"] == 10**18 + 1
    p["ma_time"] = 872542 + 1

    with boa.env.prank(factory_admin):

        with boa.env.anchor():
            _apply_new_params(swap, p)
            logs = swap.get_logs()[0]

            # values revert to contract's storage values:
            assert logs.args[3] == params["allowed_extra_profit"]
            assert logs.args[4] == params["adjustment_step"]
            assert logs.args[5] == params["ma_time"]

        with boa.reverts("MA time should be longer than 60/ln(2)"):
            p["ma_time"] = 86
            _apply_new_params(swap, p)


def test_revert_unauthorised_commit(swap, user, params):

    with boa.env.prank(user), boa.reverts(dev="only owner"):
        _apply_new_params(swap, params)
