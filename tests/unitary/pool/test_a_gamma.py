def test_A_gamma(swap):
    
    A, gamma = swap.A_gamma()

    assert A == 135 * 3**3 * 10000
    assert gamma == int(7e-5 * 1e18)
