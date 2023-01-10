def test_A_gamma(swap):

    assert swap.A() == 135 * 3**3 * 10000
    assert swap.gamma() == int(7e-5 * 1e18)
