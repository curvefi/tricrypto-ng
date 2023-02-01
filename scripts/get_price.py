def get_price(x1, x2, x3, d, gamma, A):

    a = (
        d**9 * (1 + gamma) * (-1 + gamma * (-2 + (-1 + 27 * A) * gamma))
        + 81
        * d**6
        * (1 + gamma * (2 + gamma + 9 * A * gamma))
        * x1
        * x2
        * x3
        - 2187 * d**3 * (1 + gamma) * x1**2 * x2**2 * x3**2
        + 19683 * x1**3 * x2**3 * x3**3
    )
    b = 729 * A * d**5 * gamma**2 * x1 * x2 * x3
    c = 27 * A * d**8 * gamma**2 * (1 + gamma)

    return (x2 * (a - b * (x2 + x3) - c * (2 * x1 + x2 + x3))) / (
        x1 * (-a + b * (x1 + x3) + c * (x1 + 2 * x2 + x3))
    )
