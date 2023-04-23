# @version 0.3.7

# (c) Curve.Fi, 2023
# AMM Math for 3-coin Curve Cryptoswap Pools
#
# Unless otherwise agreed on, only contracts owned by Curve DAO or
# Swiss Stake GmbH are allowed to call this contract.

"""
@title CurveTricryptoMathOptimized
@license MIT
@author Curve.Fi
@notice Curve AMM Math for 3 unpegged assets (e.g. ETH, BTC, USD).
"""

N_COINS: constant(uint256) = 3
A_MULTIPLIER: constant(uint256) = 10000

MIN_GAMMA: constant(uint256) = 10**10
MAX_GAMMA: constant(uint256) = 5 * 10**16

MIN_A: constant(uint256) = N_COINS**N_COINS * A_MULTIPLIER / 100
MAX_A: constant(uint256) = N_COINS**N_COINS * A_MULTIPLIER * 1000

version: public(constant(String[8])) = "v2.0.0"


# ------------------------ AMM math functions --------------------------------


@external
@view
def get_y(
    _ANN: uint256, _gamma: uint256, x: uint256[N_COINS], _D: uint256, i: uint256
) -> uint256[2]:
    """
    @notice Calculate x[i] given other balances x[0..N_COINS-1] and invariant D.
    @dev ANN = A * N**N . AMM contract's A is actuall ANN.
    @param _ANN AMM.A() value.
    @param _gamma AMM.gamma() value.
    @param x Balances multiplied by prices and precisions of all coins.
    @param _D Invariant.
    @param i Index of coin to calculate y.
    """

    # Safety checks
    assert _ANN > MIN_A - 1 and _ANN < MAX_A + 1, "dev: unsafe values A"
    assert _gamma > MIN_GAMMA - 1 and _gamma < MAX_GAMMA + 1, "dev: unsafe values gamma"
    assert _D > 10**17 - 1 and _D < 10**15 * 10**18 + 1, "dev: unsafe values D"

    frac: uint256 = 0
    for k in range(3):
        if k != i:
            frac = x[k] * 10**18 / _D
            assert frac > 10**16 - 1 and frac < 10**20 + 1, "dev: unsafe values x[i]"
            # if above conditions are met, x[k] > 0

    j: uint256 = 0
    k: uint256 = 0
    if i == 0:
        j = 1
        k = 2
    elif i == 1:
        j = 0
        k = 2
    elif i == 2:
        j = 0
        k = 1

    ANN: int256 = convert(_ANN, int256)
    gamma: int256 = convert(_gamma, int256)
    D: int256 = convert(_D, int256)
    x_j: int256 = convert(x[j], int256)
    x_k: int256 = convert(x[k], int256)
    gamma2: int256 = unsafe_mul(gamma, gamma)

    a: int256 = 10**36 / 27

    # 10**36/9 + 2*10**18*gamma/27 - D**2/x_j*gamma**2*ANN/27**2/convert(A_MULTIPLIER, int256)/x_k
    b: int256 = (
        unsafe_add(
            10**36 / 9,
            unsafe_div(unsafe_mul(2 * 10**18, gamma), 27)
        )
        - unsafe_div(
            unsafe_div(
                unsafe_div(
                    unsafe_mul(
                        unsafe_div(unsafe_mul(D, D), x_j),
                        gamma2
                    ) * ANN,
                    27**2
                ),
                convert(A_MULTIPLIER, int256)
            ),
            x_k,
        )
    )  # <------- The first two expressions can be unsafe, and unsafely added.

    # 10**36/9 + gamma*(gamma + 4*10**18)/27 + gamma**2*(x_j+x_k-D)/D*ANN/27/convert(A_MULTIPLIER, int256)
    c: int256 = (
        unsafe_add(
            10**36 / 9,
            unsafe_div(unsafe_mul(gamma, unsafe_add(gamma, 4 * 10**18)), 27)
        )
        + unsafe_div(
            unsafe_div(
                unsafe_mul(
                    unsafe_div(gamma2 * unsafe_sub(unsafe_add(x_j, x_k), D), D),
                    ANN
                ),
                27
            ),
            convert(A_MULTIPLIER, int256),
        )
    )  # <--------- Same as above with the first two expressions. In the third
    #   expression, x_j + x_k will not overflow since we know their range from
    #                                              previous assert statements.

    # (10**18 + gamma)**2/27
    d: int256 = unsafe_div(unsafe_add(10**18, gamma)**2, 27)

    # abs(3*a*c/b - b)
    d0: int256 = abs(unsafe_mul(3, a) * c / b - b)  # <------------ a is smol.

    divider: int256 = 0
    if d0 > 10**48:
        divider = 10**30
    elif d0 > 10**44:
        divider = 10**26
    elif d0 > 10**40:
        divider = 10**22
    elif d0 > 10**36:
        divider = 10**18
    elif d0 > 10**32:
        divider = 10**14
    elif d0 > 10**28:
        divider = 10**10
    elif d0 > 10**24:
        divider = 10**6
    elif d0 > 10**20:
        divider = 10**2
    else:
        divider = 1

    additional_prec: int256 = 0
    if abs(a) > abs(b):
        additional_prec = abs(unsafe_div(a, b))
        a = unsafe_div(unsafe_mul(a, additional_prec), divider)
        b = unsafe_div(b * additional_prec, divider)
        c = unsafe_div(c * additional_prec, divider)
        d = unsafe_div(d * additional_prec, divider)
    else:
        additional_prec = abs(unsafe_div(b, a))
        a = unsafe_div(a / additional_prec, divider)
        b = unsafe_div(unsafe_div(b, additional_prec), divider)
        c = unsafe_div(unsafe_div(c, additional_prec), divider)
        d = unsafe_div(unsafe_div(d, additional_prec), divider)

    # 3*a*c/b - b
    _3ac: int256 = unsafe_mul(3, a) * c
    delta0: int256 = unsafe_div(_3ac, b) - b

    # 9*a*c/b - 2*b - 27*a**2/b*d/b
    delta1: int256 = (
        unsafe_div(3 * _3ac, b)
        - unsafe_mul(2, b)
        - unsafe_div(unsafe_div(27 * a**2, b) * d, b)
    )

    # delta1**2 + 4*delta0**2/b*delta0
    sqrt_arg: int256 = (
        delta1**2 +
        unsafe_div(4 * delta0**2, b) * delta0
    )

    sqrt_val: int256 = 0
    if sqrt_arg > 0:
        sqrt_val = convert(isqrt(convert(sqrt_arg, uint256)), int256)
    else:
        return [self._newton_y(_ANN, _gamma, x, _D, i), 0]

    b_cbrt: int256 = 0
    if b >= 0:
        b_cbrt = convert(self._cbrt(convert(b, uint256)), int256)
    else:
        b_cbrt = -convert(self._cbrt(convert(-b, uint256)), int256)

    second_cbrt: int256 = 0
    if delta1 > 0:
        # convert(self._cbrt(convert((delta1 + sqrt_val), uint256)/2), int256)
        second_cbrt = convert(
            self._cbrt(unsafe_div(convert(delta1 + sqrt_val, uint256), 2)),
            int256
        )
    else:
        second_cbrt = -convert(
            self._cbrt(unsafe_div(convert(-(delta1 - sqrt_val), uint256), 2)),
            int256
        )

    # b_cbrt*b_cbrt/10**18*second_cbrt/10**18
    C1: int256 = unsafe_div(
        unsafe_div(b_cbrt * b_cbrt, 10**18) * second_cbrt,
        10**18
    )

    # (b + b*delta0/C1 - C1)/3
    root_K0: int256 = unsafe_div(b + b * delta0 / C1 - C1, 3)

    # D*D/27/x_k*D/x_j*root_K0/a
    root: int256 = unsafe_div(
        unsafe_div(
            unsafe_div(unsafe_div(D * D, 27), x_k) * D,
            x_j
        ) * root_K0,
        a
    )

    out: uint256[2] = [
        convert(root, uint256),
        convert(unsafe_div(10**18 * root_K0, a), uint256)
    ]

    frac = unsafe_div(out[0] * 10**18, _D)
    assert frac >= 10**16 - 1 and frac < 10**20 + 1, "dev: unsafe value for y"
    # due to precision issues, get_y can be off by 2 wei or so wrt _newton_y

    return out


@internal
@view
def _newton_y(
    ANN: uint256, gamma: uint256, x: uint256[N_COINS], D: uint256, i: uint256
) -> uint256:

    # Calculate x[i] given A, gamma, xp and D using newton's method.
    # This is the original method; get_y replaces it, but defaults to
    # this version conditionally.

    # We can ignore safuty checks since they are already done in get_y

    frac: uint256 = 0
    for k in range(3):
        if k != i:
            frac = x[k] * 10**18 / D
            assert frac > 10**16 - 1 and frac < 10**20 + 1, "dev: unsafe values x[i]"

    y: uint256 = D / N_COINS
    K0_i: uint256 = 10**18
    S_i: uint256 = 0

    x_sorted: uint256[N_COINS] = x
    x_sorted[i] = 0
    x_sorted = self._sort(x_sorted)  # From high to low

    convergence_limit: uint256 = max(max(x_sorted[0] / 10**14, D / 10**14), 100)

    for j in range(2, N_COINS + 1):
        _x: uint256 = x_sorted[N_COINS - j]
        y = y * D / (_x * N_COINS)  # Small _x first
        S_i += _x

    for j in range(N_COINS - 1):
        K0_i = K0_i * x_sorted[j] * N_COINS / D  # Large _x first

    # initialise variables:
    diff: uint256 = 0
    y_prev: uint256 = 0
    K0: uint256 = 0
    S: uint256 = 0
    _g1k0: uint256 = 0
    mul1: uint256 = 0
    mul2: uint256 = 0
    yfprime: uint256 = 0
    _dyfprime: uint256 = 0
    fprime: uint256 = 0
    y_minus: uint256 = 0
    y_plus: uint256 = 0

    for j in range(255):
        y_prev = y

        K0 = K0_i * y * N_COINS / D
        S = S_i + y

        _g1k0 = gamma + 10**18
        if _g1k0 > K0:
            _g1k0 = _g1k0 - K0 + 1
        else:
            _g1k0 = K0 - _g1k0 + 1

        # mul1 = 10**18 * D / gamma * _g1k0 / gamma * _g1k0 * A_MULTIPLIER / ANN
        mul1 = 10**18 * D / gamma * _g1k0 / gamma * _g1k0 * A_MULTIPLIER / ANN

        # 2*K0 / _g1k0
        mul2 = 10**18 + (2 * 10**18) * K0 / _g1k0

        yfprime = 10**18 * y + S * mul2 + mul1
        _dyfprime = D * mul2
        if yfprime < _dyfprime:
            y = y_prev / 2
            continue
        else:
            yfprime -= _dyfprime

        fprime = yfprime / y

        # y -= f / f_prime;  y = (y * fprime - f) / fprime
        y_minus = mul1 / fprime
        y_plus = (yfprime + 10**18 * D) / fprime + y_minus * 10**18 / K0
        y_minus += 10**18 * S / fprime

        if y_plus < y_minus:
            y = y_prev / 2
        else:
            y = y_plus - y_minus

        if y > y_prev:
            diff = y - y_prev
        else:
            diff = y_prev - y

        if diff < max(convergence_limit, y / 10**14):
            frac = y * 10**18 / D
            assert frac > 10**16 - 1 and frac < 10**20 + 1, "dev: unsafe value for y"
            return y

    raise "Did not converge"


@external
@view
def newton_D(
    ANN: uint256,
    gamma: uint256,
    x_unsorted: uint256[N_COINS],
    K0_prev: uint256 = 0,
) -> uint256:
    """
    @notice Finding the invariant via newtons method using good initial guesses.
    @dev ANN is higher by the factor A_MULTIPLIER
    @dev ANN is already A * N**N
    @param ANN the A * N**N value
    @param gamma the gamma value
    @param x_unsorted the array of coin balances (not sorted)
    @param K0_prev apriori for newton's method derived from get_y_int. Defaults
           to zero (no apriori)
    """
    x: uint256[N_COINS] = self._sort(x_unsorted)
    assert x[0] < max_value(uint256) / 10**18 * N_COINS**N_COINS, "dev: out of limits"
    assert x[0] > 0, "dev: empty pool"

    # Safe to do unsafe add since we checked largest x's bounds previously
    S: uint256 = unsafe_add(unsafe_add(x[0], x[1]), x[2])
    D: uint256 = 0

    if K0_prev == 0:
        # Geometric mean of 3 numbers cannot be larger than the largest number
        # so the following is safe to do:
        D = unsafe_mul(N_COINS, self._geometric_mean(x))
    else:
        if S > 10**36:
            D = self._cbrt(
                unsafe_div(
                    unsafe_div(x[0] * x[1], 10**36) * x[2],
                    K0_prev
                ) * 27 * 10**12
            )
        elif S > 10**24:
            D = self._cbrt(
                unsafe_div(
                    unsafe_div(x[0] * x[1], 10**24) * x[2],
                    K0_prev
                ) * 27 * 10**6
            )
        else:
            D = self._cbrt(
                unsafe_div(
                    unsafe_div(x[0] * x[1], 10**18) * x[2],
                    K0_prev
                ) * 27
            )

        # D not zero here if K0_prev > 0, and we checked if x[0] is gt 0.

    # initialise variables:
    K0: uint256 = 0
    _g1k0: uint256 = 0
    mul1: uint256 = 0
    mul2: uint256 = 0
    neg_fprime: uint256 = 0
    D_plus: uint256 = 0
    D_minus: uint256 = 0
    D_prev: uint256 = 0

    diff: uint256 = 0
    frac: uint256 = 0

    for i in range(255):

        D_prev = D

        # K0 = 10**18 * x[0] * N_COINS / D * x[1] * N_COINS / D * x[2] * N_COINS / D
        K0 = unsafe_div(
            unsafe_mul(
                unsafe_mul(
                    unsafe_div(
                        unsafe_mul(
                            unsafe_mul(
                                unsafe_div(
                                    unsafe_mul(
                                        unsafe_mul(10**18, x[0]), N_COINS
                                    ),
                                    D,
                                ),
                                x[1],
                            ),
                            N_COINS,
                        ),
                        D,
                    ),
                    x[2],
                ),
                N_COINS,
            ),
            D,
        )  # <-------- We can convert the entire expression using unsafe math.
        #   since x_i is not too far from D, so overflow is not expected. Also
        #      D > 0, since we proved that already. unsafe_div is safe. K0 > 0
        #        since we can safely assume that D < 10**18 * x[0]. K0 is also
        #                            in the range of 10**18 (it's a property).

        _g1k0 = unsafe_add(gamma, 10**18)  # <--------- safe to do unsafe_add.

        if _g1k0 > K0:  #       The following operations can safely be unsafe.
            _g1k0 = unsafe_add(unsafe_sub(_g1k0, K0), 1)
        else:
            _g1k0 = unsafe_add(unsafe_sub(K0, _g1k0), 1)

        # D / (A * N**N) * _g1k0**2 / gamma**2
        # mul1 = 10**18 * D / gamma * _g1k0 / gamma * _g1k0 * A_MULTIPLIER / ANN
        mul1 = unsafe_div(
            unsafe_mul(
                unsafe_mul(
                    unsafe_div(
                        unsafe_mul(
                            unsafe_div(unsafe_mul(10**18, D), gamma), _g1k0
                        ),
                        gamma,
                    ),
                    _g1k0,
                ),
                A_MULTIPLIER,
            ),
            ANN,
        )  # <------ Since D > 0, gamma is small, _g1k0 is small, the rest are
        #        non-zero and small constants, and D has a cap in this method,
        #                    we can safely convert everything to unsafe maths.

        # 2*N*K0 / _g1k0
        # mul2 = (2 * 10**18) * N_COINS * K0 / _g1k0
        mul2 = unsafe_div(
            unsafe_mul(2 * 10**18 * N_COINS, K0), _g1k0
        )  # <--------------- K0 is approximately around D, which has a cap of
        #      10**15 * 10**18 + 1, since we get that in get_y which is called
        #    with newton_D. _g1k0 > 0, so the entire expression can be unsafe.

        # neg_fprime: uint256 = (S + S * mul2 / 10**18) + mul1 * N_COINS / K0 - mul2 * D / 10**18
        neg_fprime = unsafe_sub(
            unsafe_add(
                unsafe_add(S, unsafe_div(unsafe_mul(S, mul2), 10**18)),
                unsafe_div(unsafe_mul(mul1, N_COINS), K0),
            ),
            unsafe_div(unsafe_mul(mul2, D), 10**18),
        )  # <--- mul1 is a big number but not huge: safe to unsafely multiply
        # with N_coins. neg_fprime > 0 if this expression executes.
        # mul2 is in the range of 10**18, since K0 is in that range, S * mul2
        # is safe. The first three sums can be done using unsafe math safely
        # and since the final expression will be small since mul2 is small, we
        # can safely do the entire expression unsafely.

        # D -= f / fprime
        # D * (neg_fprime + S) / neg_fprime
        D_plus = unsafe_div(D * unsafe_add(neg_fprime, S), neg_fprime)

        # D*D / neg_fprime
        D_minus = unsafe_div(D * D, neg_fprime)

        # Since we know K0 > 0, and neg_fprime > 0, several unsafe operations
        # are possible in the following. Also, (10**18 - K0) is safe to mul.
        # So the only expressions we keep safe are (D_minus + ...) and (D * ...)
        if 10**18 > K0:
            # D_minus += D * (mul1 / neg_fprime) / 10**18 * (10**18 - K0) / K0
            D_minus += unsafe_div(
                unsafe_mul(
                    unsafe_div(D * unsafe_div(mul1, neg_fprime), 10**18),
                    unsafe_sub(10**18, K0),
                ),
                K0,
            )
        else:
            # D_minus -= D * (mul1 / neg_fprime) / 10**18 * (K0 - 10**18) / K0
            D_minus -= unsafe_div(
                unsafe_mul(
                    unsafe_div(D * unsafe_div(mul1, neg_fprime), 10**18),
                    unsafe_sub(K0, 10**18),
                ),
                K0,
            )

        if D_plus > D_minus:
            D = unsafe_sub(D_plus, D_minus)  # <--------- Safe since we check.
        else:
            D = unsafe_div(unsafe_sub(D_minus, D_plus), 2)

        if D > D_prev:
            diff = unsafe_sub(D, D_prev)
        else:
            diff = unsafe_sub(D_prev, D)

        # Could reduce precision for gas efficiency here:
        if unsafe_mul(diff, 10**14) < max(10**16, D):

            # Test that we are safe with the next get_y
            for _x in x:
                frac = unsafe_div(unsafe_mul(_x, 10**18), D)
                assert frac >= 10**16 - 1 and frac < 10**20 + 1, "dev: unsafe values x[i]"

            return D
    raise "Did not converge"


@external
@view
def get_p(
    _xp: uint256[N_COINS],
    _D: uint256,
    _A_gamma: uint256[2],
) -> uint256[N_COINS - 1]:
    """
    @notice Calculates dx/dy.
    @dev Output needs to be multiplied with price_scale to get the actual value.
    @param _xp Balances of the pool.
    @param _D Current value of D.
    @param _A_gamma Amplification coefficient and gamma.
    """

    assert _D > 10**17 - 1 and _D < 10**15 * 10**18 + 1, "dev: unsafe D values"

    D: int256 = convert(_D, int256)
    ANN: int256 = convert(_A_gamma[0], int256)
    gamma: int256 = convert(_A_gamma[1], int256)
    x1: int256 = convert(_xp[0], int256)
    x2: int256 = convert(_xp[1], int256)
    x3: int256 = convert(_xp[2], int256)
    gamma2: int256 = unsafe_mul(gamma, gamma)

    # (10**18 + gamma)*(-10**18 + gamma*(-2*10**18 + (-10**18 + 10**18*A/10000)*gamma/10**18)/10**18)/10**18
    # this entire expression can be unsafe:
    s1: int256 = unsafe_div(
        unsafe_mul(
            unsafe_add(10**18, gamma),
            unsafe_add(
                -10**18,
                unsafe_div(
                    unsafe_mul(
                        gamma,
                        unsafe_add(
                            -2 * 10**18,
                            unsafe_div(
                                unsafe_mul(
                                    unsafe_add(
                                        -10**18,
                                        unsafe_div(
                                            unsafe_mul(10**18, ANN),
                                            convert(A_MULTIPLIER, int256),
                                        ),
                                    ),
                                    gamma,
                                ),
                                10**18,
                            ),
                        ),
                    ),
                    10**18,
                ),
            ),
        ),
        10**18,
    )

    # 81*(10**18 + gamma*(2*10**18 + gamma + 10**18*9*A/27/10000*gamma/10**18)/10**18)*x1/D*x2/D*x3/D
    # Multiplication by x1, x2 and x3 needs to be safe:
    s2: int256 = unsafe_div(
        unsafe_mul(
            gamma,
            unsafe_add(
                unsafe_add(2 * 10**18, gamma),
                unsafe_div(
                    unsafe_mul(
                        unsafe_div(
                            unsafe_div(
                                unsafe_mul(10**18 * 9, ANN), 27
                            ),
                            convert(A_MULTIPLIER, int256),
                        ),
                        gamma,
                    ),
                    10**18,
                ),
            )
        ),
        10**18,
    )
    s2 = unsafe_div(
        unsafe_div(
            unsafe_div(
                unsafe_mul(81, (10**18 + s2)) * x1, D
            ) * x2,
            D,
        ) * x3,
        D
    )

    # 2187*(10**18 + gamma)*x1/D*x1/D*x2/D*x2/D*x3/D*x3/D
    # Same as before: multiplication by x1, x2 or x3 should be safe
    s3: int256 = unsafe_mul(2187, unsafe_add(10**18, gamma))
    s3 = unsafe_div(
        unsafe_div(
            unsafe_div(s3 * x1, D) * x2, D
        ) * x3,
        D
    )
    s3 = unsafe_div(
        unsafe_div(
            unsafe_div(s3 * x1, D) * x2, D
        ) * x3,
        D
    )

    # 10**18*19683*x1/D*x1/D*x1/D*x2/D*x2/D*x2/D*x3/D*x3/D*x3/D
    # Same as before.
    s4: int256 = 10**18 * 19683 * x1
    s4 = unsafe_div(unsafe_div(s4, D) * x2, D) * x3
    s4 = unsafe_div(
        unsafe_div(
            unsafe_div(
                unsafe_div(
                    unsafe_div(
                        unsafe_div(
                            unsafe_div(s4, D) * x1,
                            D
                        ) * x2,
                        D
                    ) * x3,
                    D,
                ) * x1,
                D
            ) * x2,
            D
        ) * x3,
        D
    )

    a: int256 = s1 + s2 + s4 - s3

    # 10**18*729*A*x1/D*x2/D*x3/D*gamma**2/D/27/10000
    b: int256 = unsafe_div(
        unsafe_div(
            unsafe_div(
                unsafe_div(
                    unsafe_div(
                        unsafe_mul(10**18 * 27, ANN),
                        convert(A_MULTIPLIER, int256),
                    ) * x1,
                    D,
                ) * x2,
                D,
            ) * x3,
            D,
        ) * gamma2,
        D,
    )

    # 27*A*gamma**2*(10**18 + gamma)/D/27/10000
    # entire expression can be unsafe:
    c: int256 = unsafe_div(
        unsafe_div(
            unsafe_div(
                unsafe_mul(
                    27,
                    unsafe_mul(
                        ANN,
                        unsafe_mul(
                            gamma2,
                            unsafe_add(10**18, gamma)
                        )
                    )
                ),
                D
            ),
            27
        ),
        convert(A_MULTIPLIER, int256)
    )

    return [
        self._get_partial_derivative(x2, x1, x3, a, b, c),
        self._get_partial_derivative(x3, x1, x2, a, b, c),
    ]


@internal
@view
def _get_partial_derivative(
    x1: int256,
    x2: int256,
    x3: int256,
    a: int256,
    b: int256,
    c: int256,
) -> uint256:

    # (
    #    (10**18*x2*( 10**18*a - b*(x2 + x3)/10**18 - c*(2*x1 + x2 + x3)/10**18))
    #    /
    #    (x1*(-10**18*a + b*(x1 + x3)/10**18 + c*(x1 + 2*x2 + x3)/10**18))
    # )

    numerator_a: int256 = 10**18 * x2
    numerator_b: int256 = (
            10**18 * a
            - unsafe_div(b * (x2 + x3), 10**18)
            - unsafe_div(c * (unsafe_mul(2, x1) + unsafe_add(x2, x3)), 10**18)
        )

    denominator: int256 = (
        x1
        * (
            unsafe_mul(-10**18, a)  # <--- since we did safemul before
            + unsafe_div(b * (x1 + x3), 10**18)
            + unsafe_div(c * (unsafe_mul(2, x2) + unsafe_add(x1, x3)), 10**18)
        )
    )

    # check sign to ensure it is negative:
    sign_num_a: int256 = -1
    sign_num_b: int256 = -1
    sign_denom: int256 = -1
    if numerator_a > 0:
        sign_num_a = 1
    if numerator_b > 0:
        sign_num_b = 1
    if denominator > 0:
        sign_denom = 1

    assert unsafe_div(unsafe_mul(sign_num_a, sign_num_b), sign_denom) < 0, "dev: partial derivative cannot be positive"

    return self._snekmate_mul_div(
        convert(abs(numerator_a), uint256),
        convert(abs(numerator_b), uint256),
        convert(abs(denominator), uint256),
        False
    )


# --------------------------- Math Utils -------------------------------------


@external
@view
def cbrt(x: uint256) -> uint256:
    """
    @notice Calculate the cubic root of a number in 1e18 precision
    @dev Consumes around 1500 gas units
    @param x The number to calculate the cubic root of
    """
    return self._cbrt(x)


@external
@view
def geometric_mean(_x: uint256[3]) -> uint256:
    """
    @notice Calculate the geometric mean of a list of numbers in 1e18 precision.
    @param _x list of 3 numbers to sort
    """
    return self._geometric_mean(_x)


@external
@view
def reduction_coefficient(x: uint256[N_COINS], fee_gamma: uint256) -> uint256:
    """
    @notice Calculates the reduction coefficient for the given x and fee_gamma
    @dev This method is used for calculating fees.
    @param x The x values
    @param fee_gamma The fee gamma value
    """
    return self._reduction_coefficient(x, fee_gamma)


@external
@view
def wad_exp(_power: int256) -> uint256:
    """
    @notice Calculates the e**x with 1e18 precision
    @param _power The number to calculate the exponential of
    """
    return self._exp(_power)


@internal
@pure
def _reduction_coefficient(x: uint256[N_COINS], fee_gamma: uint256) -> uint256:

    # fee_gamma / (fee_gamma + (1 - K))
    # where
    # K = prod(x) / (sum(x) / N)**N
    # (all normalized to 1e18)

    S: uint256 = x[0] + x[1] + x[2]

    # Could be good to pre-sort x, but it is used only for dynamic fee
    K: uint256 = 10**18 * N_COINS * x[0] / S
    K = unsafe_div(K * N_COINS * x[1], S)  # <- unsafe div is safu.
    K = unsafe_div(K * N_COINS * x[2], S)

    if fee_gamma > 0:
        K = fee_gamma * 10**18 / (fee_gamma + 10**18 - K)

    return K


@internal
@pure
def _exp(_power: int256) -> uint256:

    # This implementation is borrowed from transmissions11 and Remco Bloemen:
    # https://github.com/transmissions11/solmate/blob/main/src/utils/SignedWadMath.sol
    # Method: wadExp

    if _power <= -42139678854452767551:
        return 0

    if _power >= 135305999368893231589:
        raise "exp overflow"

    x: int256 = unsafe_div(unsafe_mul(_power, 2**96), 10**18)

    k: int256 = unsafe_div(
        unsafe_add(
            unsafe_div(unsafe_mul(x, 2**96), 54916777467707473351141471128),
            2**95,
        ),
        2**96,
    )
    x = unsafe_sub(x, unsafe_mul(k, 54916777467707473351141471128))

    y: int256 = unsafe_add(x, 1346386616545796478920950773328)
    y = unsafe_add(
        unsafe_div(unsafe_mul(y, x), 2**96), 57155421227552351082224309758442
    )
    p: int256 = unsafe_sub(unsafe_add(y, x), 94201549194550492254356042504812)
    p = unsafe_add(
        unsafe_div(unsafe_mul(p, y), 2**96),
        28719021644029726153956944680412240,
    )
    p = unsafe_add(
        unsafe_mul(p, x), (4385272521454847904659076985693276 * 2**96)
    )

    q: int256 = x - 2855989394907223263936484059900
    q = unsafe_add(unsafe_div(unsafe_mul(q, x), 2**96), 50020603652535783019961831881945)
    q = unsafe_sub(unsafe_div(unsafe_mul(q, x), 2**96), 533845033583426703283633433725380)
    q = unsafe_add(
        unsafe_div(unsafe_mul(q, x), 2**96),
        3604857256930695427073651918091429,
    )
    q = unsafe_sub(
        unsafe_div(unsafe_mul(q, x), 2**96),
        14423608567350463180887372962807573,
    )
    q = unsafe_add(
        unsafe_div(unsafe_mul(q, x), 2**96),
        26449188498355588339934803723976023,
    )

    return shift(
        unsafe_mul(
            convert(unsafe_div(p, q), uint256),
            3822833074963236453042738258902158003155416615667,
        ),
        unsafe_sub(k, 195),
    )


@internal
@pure
def _snekmate_log_2(x: uint256, roundup: bool) -> uint256:
    """
    @notice An `internal` helper function that returns the log in base 2
         of `x`, following the selected rounding direction.
    @dev This implementation is derived from Snekmate, which is authored
         by pcaversaccio (Snekmate), distributed under the AGPL-3.0 license.
         https://github.com/pcaversaccio/snekmate
    @dev Note that it returns 0 if given 0. The implementation is
         inspired by OpenZeppelin's implementation here:
         https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/math/Math.sol.
    @param x The 32-byte variable.
    @param roundup The Boolean variable that specifies whether
           to round up or not. The default `False` is round down.
    @return uint256 The 32-byte calculation result.
    """
    value: uint256 = x
    result: uint256 = empty(uint256)

    # The following lines cannot overflow because we have the well-known
    # decay behaviour of `log_2(max_value(uint256)) < max_value(uint256)`.
    if (shift(x, -128) != empty(uint256)):
        value = shift(x, -128)
        result = 128
    if (shift(value, -64) != empty(uint256)):
        value = shift(value, -64)
        result = unsafe_add(result, 64)
    if (shift(value, -32) != empty(uint256)):
        value = shift(value, -32)
        result = unsafe_add(result, 32)
    if (shift(value, -16) != empty(uint256)):
        value = shift(value, -16)
        result = unsafe_add(result, 16)
    if (shift(value, -8) != empty(uint256)):
        value = shift(value, -8)
        result = unsafe_add(result, 8)
    if (shift(value, -4) != empty(uint256)):
        value = shift(value, -4)
        result = unsafe_add(result, 4)
    if (shift(value, -2) != empty(uint256)):
        value = shift(value, -2)
        result = unsafe_add(result, 2)
    if (shift(value, -1) != empty(uint256)):
        result = unsafe_add(result, 1)

    if (roundup and (shift(1, convert(result, int256)) < x)):
        result = unsafe_add(result, 1)

    return result


@internal
@pure
def _cbrt(x: uint256) -> uint256:

    xx: uint256 = 0
    if x >= 115792089237316195423570985008687907853269 * 10**18:
        xx = x
    elif x >= 115792089237316195423570985008687907853269:
        xx = unsafe_mul(x, 10**18)
    else:
        xx = unsafe_mul(x, 10**36)

    log2x: int256 = convert(self._snekmate_log_2(xx, False), int256)

    # When we divide log2x by 3, the remainder is (log2x % 3).
    # So if we just multiply 2**(log2x/3) and discard the remainder to calculate our
    # guess, the newton method will need more iterations to converge to a solution,
    # since it is missing that precision. It's a few more calculations now to do less
    # calculations later:
    # pow = log2(x) // 3
    # remainder = log2(x) % 3
    # initial_guess = 2 ** pow * cbrt(2) ** remainder
    # substituting -> 2 = 1.26 ≈ 1260 / 1000, we get:
    #
    # initial_guess = 2 ** pow * 1260 ** remainder // 1000 ** remainder

    remainder: uint256 = convert(log2x, uint256) % 3
    a: uint256 = unsafe_div(
        unsafe_mul(
            pow_mod256(2, unsafe_div(convert(log2x, uint256), 3)),  # <- pow
            pow_mod256(1260, remainder),
        ),
        pow_mod256(1000, remainder),
    )

    # Because we chose good initial values for cube roots, 7 newton raphson iterations
    # are just about sufficient. 6 iterations would result in non-convergences, and 8
    # would be one too many iterations. Without initial values, the iteration count
    # can go up to 20 or greater. The iterations are unrolled. This reduces gas costs
    # but takes up more bytecode:
    a = unsafe_div(unsafe_add(unsafe_mul(2, a), unsafe_div(xx, unsafe_mul(a, a))), 3)
    a = unsafe_div(unsafe_add(unsafe_mul(2, a), unsafe_div(xx, unsafe_mul(a, a))), 3)
    a = unsafe_div(unsafe_add(unsafe_mul(2, a), unsafe_div(xx, unsafe_mul(a, a))), 3)
    a = unsafe_div(unsafe_add(unsafe_mul(2, a), unsafe_div(xx, unsafe_mul(a, a))), 3)
    a = unsafe_div(unsafe_add(unsafe_mul(2, a), unsafe_div(xx, unsafe_mul(a, a))), 3)
    a = unsafe_div(unsafe_add(unsafe_mul(2, a), unsafe_div(xx, unsafe_mul(a, a))), 3)
    a = unsafe_div(unsafe_add(unsafe_mul(2, a), unsafe_div(xx, unsafe_mul(a, a))), 3)

    if x >= 115792089237316195423570985008687907853269 * 10**18:
        a = unsafe_mul(a, 10**12)
    elif x >= 115792089237316195423570985008687907853269:
        a = unsafe_mul(a, 10**6)

    return a


@internal
@pure
def _sort(unsorted_x: uint256[3]) -> uint256[3]:

    # Sorts a three-array number in a descending order:

    x: uint256[N_COINS] = unsorted_x
    temp_var: uint256 = x[0]
    if x[0] < x[1]:
        x[0] = x[1]
        x[1] = temp_var
    if x[0] < x[2]:
        temp_var = x[0]
        x[0] = x[2]
        x[2] = temp_var
    if x[1] < x[2]:
        temp_var = x[1]
        x[1] = x[2]
        x[2] = temp_var

    return x


@internal
@view
def _geometric_mean(_x: uint256[3]) -> uint256:

    # calculates a geometric mean for three numbers.

    prod: uint256 = unsafe_div(
        unsafe_div(_x[0] * _x[1], 10**18) * _x[2],
        10**18
    )

    if prod == 0:
        return 0

    return self._cbrt(prod)


@internal
@pure
def _snekmate_mul_div(
    x: uint256, y: uint256, denominator: uint256, roundup: bool
) -> uint256:
    """
    @notice Calculates "(x * y) / denominator" in 512-bit precision,
         following the selected rounding direction.
    @dev This implementation is derived from Snekmate, which is authored
         by pcaversaccio (Snekmate), distributed under the AGPL-3.0 license.
         https://github.com/pcaversaccio/snekmate
    @dev The implementation is inspired by Remco Bloemen's
         implementation under the MIT license here:
         https://xn--2-umb.com/21/muldiv.
         Furthermore, the rounding direction design pattern is
         inspired by OpenZeppelin's implementation here:
         https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/utils/math/Math.sol.
    @param x The 32-byte multiplicand.
    @param y The 32-byte multiplier.
    @param denominator The 32-byte divisor.
    @param roundup The Boolean variable that specifies whether
           to round up or not. The default `False` is round down.
    @return uint256 The 32-byte calculation result.
    """
    # Handle division by zero.
    assert denominator != empty(uint256), "Math: mul_div division by zero"

    # 512-bit multiplication "[prod1 prod0] = x * y".
    # Compute the product "mod 2**256" and "mod 2**256 - 1".
    # Then use the Chinese Remainder theorem to reconstruct
    # the 512-bit result. The result is stored in two 256-bit
    # variables, where: "product = prod1 * 2**256 + prod0".
    mm: uint256 = uint256_mulmod(x, y, max_value(uint256))
    # The least significant 256 bits of the product.
    prod0: uint256 = unsafe_mul(x, y)
    # The most significant 256 bits of the product.
    prod1: uint256 = empty(uint256)

    if (mm < prod0):
        prod1 = unsafe_sub(unsafe_sub(mm, prod0), 1)
    else:
        prod1 = unsafe_sub(mm, prod0)

    # Handling of non-overflow cases, 256 by 256 division.
    if (prod1 == empty(uint256)):
        if (roundup and uint256_mulmod(x, y, denominator) != empty(uint256)):
            # Calculate "ceil((x * y) / denominator)". The following
            # line cannot overflow because we have the previous check
            # "(x * y) % denominator != 0", which accordingly rules out
            # the possibility of "x * y = 2**256 - 1" and `denominator == 1`.
            return unsafe_add(unsafe_div(prod0, denominator), 1)
        else:
            return unsafe_div(prod0, denominator)

    # Ensure that the result is less than 2**256. Also,
    # prevents that `denominator == 0`.
    assert denominator > prod1, "Math: mul_div overflow"

    #######################
    # 512 by 256 Division #
    #######################

    # Make division exact by subtracting the remainder
    # from "[prod1 prod0]". First, compute remainder using
    # the `uint256_mulmod` operation.
    remainder: uint256 = uint256_mulmod(x, y, denominator)

    # Second, subtract the 256-bit number from the 512-bit
    # number.
    if (remainder > prod0):
        prod1 = unsafe_sub(prod1, 1)
    prod0 = unsafe_sub(prod0, remainder)

    # Factor powers of two out of the denominator and calculate
    # the largest power of two divisor of denominator. Always `>= 1`,
    # unless the denominator is zero (which is prevented above),
    # in which case `twos` is zero. For more details, please refer to:
    # https://cs.stackexchange.com/q/138556.

    # The following line does not overflow because the denominator
    # cannot be zero at this stage of the function.
    twos: uint256 = denominator & (unsafe_add(~denominator, 1))
    # Divide denominator by `twos`.
    denominator_div: uint256 = unsafe_div(denominator, twos)
    # Divide "[prod1 prod0]" by `twos`.
    prod0 = unsafe_div(prod0, twos)
    # Flip `twos` such that it is "2**256 / twos". If `twos` is zero,
    # it becomes one.
    twos = unsafe_add(unsafe_div(unsafe_sub(empty(uint256), twos), twos), 1)

    # Shift bits from `prod1` to `prod0`.
    prod0 |= unsafe_mul(prod1, twos)

    # Invert the denominator "mod 2**256". Since the denominator is
    # now an odd number, it has an inverse modulo 2**256, so we have:
    # "denominator * inverse = 1 mod 2**256". Calculate the inverse by
    # starting with a seed that is correct for four bits. That is,
    # "denominator * inverse = 1 mod 2**4".
    inverse: uint256 = unsafe_mul(3, denominator_div) ^ 2

    # Use Newton-Raphson iteration to improve accuracy. Thanks to Hensel's
    # lifting lemma, this also works in modular arithmetic by doubling the
    # correct bits in each step.
    inverse = unsafe_mul(inverse, unsafe_sub(2, unsafe_mul(denominator_div, inverse))) # Inverse "mod 2**8".
    inverse = unsafe_mul(inverse, unsafe_sub(2, unsafe_mul(denominator_div, inverse))) # Inverse "mod 2**16".
    inverse = unsafe_mul(inverse, unsafe_sub(2, unsafe_mul(denominator_div, inverse))) # Inverse "mod 2**32".
    inverse = unsafe_mul(inverse, unsafe_sub(2, unsafe_mul(denominator_div, inverse))) # Inverse "mod 2**64".
    inverse = unsafe_mul(inverse, unsafe_sub(2, unsafe_mul(denominator_div, inverse))) # Inverse "mod 2**128".
    inverse = unsafe_mul(inverse, unsafe_sub(2, unsafe_mul(denominator_div, inverse))) # Inverse "mod 2**256".

    # Since the division is now exact, we can divide by multiplying
    # with the modular inverse of the denominator. This returns the
    # correct result modulo 2**256. Since the preconditions guarantee
    # that the result is less than 2**256, this is the final result.
    # We do not need to calculate the high bits of the result and
    # `prod1` is no longer necessary.
    result: uint256 = unsafe_mul(prod0, inverse)

    if (roundup and uint256_mulmod(x, y, denominator) != empty(uint256)):
        # Calculate "ceil((x * y) / denominator)". The following
        # line uses intentionally checked arithmetic to prevent
        # a theoretically possible overflow.
        result += 1

    return result
