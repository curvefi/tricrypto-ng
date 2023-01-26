import boa


def test_A_gamma(swap):

    A = swap.A()
    gamma = swap.gamma()

    assert A == 135 * 3**3 * 10000
    assert gamma == int(7e-5 * 1e18)


# https://github.com/curvefi/curve-factory-crypto/blob/master/tests/test_a_gamma.py
def test_ramp_A_gamma(swap, factory_admin):

    A = swap.A()
    gamma = swap.gamma()
    A_gamma_initial = [A, gamma]

    future_A = 180 * 2**2 * 10000
    future_gamma = int(5e-4 * 1e18)
    t0 = boa.env.vm.state.timestamp
    t1 = t0 + 7 * 86400

    with boa.env.prank(factory_admin):
        swap.ramp_A_gamma(future_A, future_gamma, t1)

    for i in range(1, 8):
        boa.env.time_travel(86400)
        A_gamma = [swap.A(), swap.gamma()]
        assert (
            abs(
                A_gamma[0]
                - (
                    A_gamma_initial[0]
                    + (future_A - A_gamma_initial[0]) * i / 7
                )
            )
            < 1e-4 * A_gamma_initial[0]
        )
        assert (
            abs(
                A_gamma[1]
                - (
                    A_gamma_initial[1]
                    + (future_gamma - A_gamma_initial[1]) * i / 7
                )
            )
            < 1e-4 * A_gamma_initial[1]
        )
