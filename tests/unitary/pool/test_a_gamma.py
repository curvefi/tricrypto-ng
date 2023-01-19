def test_A_gamma(swap):

    A, gamma = swap.A_gamma()

    assert A == 135 * 3**3 * 10000
    assert gamma == int(7e-5 * 1e18)


# https://github.com/curvefi/curve-factory-crypto/blob/master/tests/test_a_gamma.py
def test_ramp_A_gamma(chain, crypto_swap, accounts):
    initial_A = 90 * 2**2 * 10000
    future_A = 180 * 2**2 * 10000
    initial_gamma = int(2.8e-4 * 1e18)
    future_gamma = int(5e-4 * 1e18)
    t0 = chain.time()
    t1 = t0 + 7 * 86400
    crypto_swap.ramp_A_gamma(future_A, future_gamma, t1, {"from": accounts[0]})

    for i in range(1, 8):
        chain.sleep(86400)
        chain.mine()
        assert (
            abs(crypto_swap.A() - (initial_A + (future_A - initial_A) * i / 7))
            < 1e-4 * initial_A
        )
        assert (
            abs(
                crypto_swap.gamma()
                - (initial_gamma + (future_gamma - initial_gamma) * i / 7)
            )
            < 1e-4 * initial_gamma
        )
