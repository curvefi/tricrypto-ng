def test_A_gamma(tricrypto_swap):
    assert tricrypto_swap.A() == 135 * 3**3 * 10000
    assert tricrypto_swap.gamma() == int(7e-5 * 1e18)
