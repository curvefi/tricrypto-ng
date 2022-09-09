def test_A_gamma(crypto_swap):
    assert crypto_swap.A() == 135 * 3**3 * 10000
    assert crypto_swap.gamma() == int(7e-5 * 1e18)
