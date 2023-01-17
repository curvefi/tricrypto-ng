import boa


def test_revert_unauthorised_ramp(swap, user):

    with boa.env.prank(user), boa.reverts(dev="only owner"):
        swap.ramp_A_gamma(1, 1, 1)


def test_revert_ramp_while_ramping(swap, factory_admin):

    assert swap.initial_A_gamma_time() == 0

    A_gamma = swap.A_gamma()
    future_time = boa.env.vm.state.timestamp + 86400 + 1
    with boa.env.prank(factory_admin):
        swap.ramp_A_gamma(A_gamma[0] + 1, A_gamma[1] + 1, future_time)

        with boa.reverts(dev="ramp undergoing"):
            swap.ramp_A_gamma(A_gamma[0], A_gamma[1], future_time)


def test_revert_fast_ramps(swap, factory_admin):

    A_gamma = swap.A_gamma()
    future_time = boa.env.vm.state.timestamp + 10
    with boa.env.prank(factory_admin), boa.reverts(dev="insufficient time"):
        swap.ramp_A_gamma(A_gamma[0] + 1, A_gamma[1] + 1, future_time)


def test_revert_unauthorised_stop_ramp(swap, factory_admin, user):

    assert swap.initial_A_gamma_time() == 0

    A_gamma = swap.A_gamma()
    future_time = boa.env.vm.state.timestamp + 86400 + 1
    with boa.env.prank(factory_admin):
        swap.ramp_A_gamma(A_gamma[0] + 1, A_gamma[1] + 1, future_time)

    with boa.env.prank(user), boa.reverts(dev="only owner"):
        swap.stop_ramp_A_gamma()
