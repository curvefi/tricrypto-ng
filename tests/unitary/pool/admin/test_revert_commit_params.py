import copy

import boa


def _commit_new_params(swap, params):
    swap.commit_new_parameters(
        params["mid_fee"],
        params["out_fee"],
        params["fee_gamma"],
        params["allowed_extra_profit"],
        params["adjustment_step"],
        params["ma_time"],
    )


def test_commit_incorrect_fee_params(swap, factory_admin, params):

    p = copy.deepcopy(params)
    p["mid_fee"] = p["out_fee"] + 1
    with boa.env.prank(factory_admin):
        with boa.reverts(dev="mid-fee is too high"):
            _commit_new_params(swap, p)

        p["out_fee"] = 0
        with boa.reverts(dev="fee is out of range"):
            _commit_new_params(swap, p)

        # too large out_fee revert to old out_fee:
        p["mid_fee"] = params["mid_fee"]
        p["out_fee"] = 10**10 + 1  # <-- MAX_FEE
        _commit_new_params(swap, p)
        logs = swap.get_logs()[0]
        assert logs.args[1] == params["out_fee"]


def test_commit_incorrect_fee_gamma(swap, factory_admin, params):

    p = copy.deepcopy(params)
    p["fee_gamma"] = 0

    with boa.env.prank(factory_admin):

        with boa.reverts(dev="fee_gamma out of range [1 .. 10**18]"):
            _commit_new_params(swap, p)

        p["fee_gamma"] = 10**18 + 1
        _commit_new_params(swap, p)

    # it will not change fee_gamma as it is above 10**18
    assert swap.get_logs()[0].args[2] == params["fee_gamma"]


def test_commit_rebalancing_params(swap, factory_admin, params):

    p = copy.deepcopy(params)
    p["allowed_extra_profit"] = 10**18 + 1
    p["adjustment_step"] == 10**18 + 1
    p["ma_time"] = 872542 + 1

    with boa.env.prank(factory_admin):

        with boa.env.anchor():
            _commit_new_params(swap, p)

        logs = swap.get_logs()[0]
        assert logs.args[3] == params["allowed_extra_profit"]
        assert logs.args[4] == params["adjustment_step"]
        assert logs.args[5] == params["ma_time"]

        with boa.reverts(dev="MA time should be longer than 60/ln(2)"):
            p["ma_time"] = 86
            _commit_new_params(swap, p)


def test_revert_commit_twice(swap, factory_admin, params):

    with boa.env.prank(factory_admin):
        _commit_new_params(swap, params)

        with boa.reverts(dev="active action"):
            _commit_new_params(swap, params)


def test_revert_unauthorised_commit(swap, user, params):

    with boa.env.prank(user), boa.reverts(dev="only owner"):
        _commit_new_params(swap, params)


def test_unauthorised_revert(swap, user, factory_admin, params):

    with boa.env.prank(factory_admin):
        _commit_new_params(swap, params)

    with boa.env.prank(user), boa.reverts(dev="only owner"):
        swap.revert_new_parameters()
