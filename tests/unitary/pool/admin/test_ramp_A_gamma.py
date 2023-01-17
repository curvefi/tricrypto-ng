import copy

import boa


def test_ramp_A_gamma_up(swap, factory_admin, params):

    p = copy.deepcopy(params)
    future_A = p["A"] + 10000000
    future_gamma = p["gamma"] + 10000000
    future_time = boa.env.vm.state.timestamp + 86400

    initial_A_gamma = swap.A_gamma()
    with boa.env.prank(factory_admin):
        swap.ramp_A_gamma(future_A, future_gamma, future_time)

    boa.env.time_travel(10000)
    current_A_gamma = swap.A_gamma()
    for i in range(2):
        assert current_A_gamma[i] > initial_A_gamma[i]

    boa.env.time_travel(76400)
    current_A_gamma = swap.A_gamma()
    assert current_A_gamma[0] == future_A
    assert current_A_gamma[1] == future_gamma


def test_ramp_A_gamma_down(swap, factory_admin, params):

    p = copy.deepcopy(params)
    future_A = p["A"] - 10000000
    future_gamma = p["gamma"] - 10000000
    future_time = boa.env.vm.state.timestamp + 86400

    initial_A_gamma = swap.A_gamma()
    with boa.env.prank(factory_admin):
        swap.ramp_A_gamma(future_A, future_gamma, future_time)

    boa.env.time_travel(10000)
    current_A_gamma = swap.A_gamma()
    for i in range(2):
        assert current_A_gamma[i] < initial_A_gamma[i]

    boa.env.time_travel(76400)
    current_A_gamma = swap.A_gamma()
    assert current_A_gamma[0] == future_A
    assert current_A_gamma[1] == future_gamma
