# @version 0.3.7
# (c) Curve.Fi, 2023
# Math for 3-coin Curve cryptoswap pools
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

version: public(constant(String[8])) = "v1.0.0"


# ------------------------ AMM math functions --------------------------------


@external
@view
def get_y(
    _ANN: uint256, _gamma: uint256, x: uint256[N_COINS], _D: uint256, i: uint256
) -> uint256[2]:
    """
    Calculating x[i] given other balances x[0..N_COINS-1] and invariant D
    ANN = A * N**N
    """
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

    a: int256 = 10**36 / 27
    b: int256 = unsafe_sub(
        unsafe_add(
            10**36 / 9, unsafe_div(unsafe_mul(2 * 10**18, gamma), 27)
        ),
        unsafe_div(
            unsafe_div(
                unsafe_div(
                    unsafe_mul(
                        unsafe_mul(unsafe_div(D**2, x_j), gamma**2), ANN
                    ),
                    27**2,
                ),
                convert(A_MULTIPLIER, int256),
            ),
            x_k,
        ),
    )
    c: int256 = unsafe_add(
        unsafe_add(
            10**36 / 9,
            unsafe_div(unsafe_mul(gamma, unsafe_add(gamma, 4 * 10**18)), 27),
        ),
        unsafe_div(
            unsafe_div(
                unsafe_mul(
                    unsafe_div(
                        gamma**2 * (unsafe_sub(unsafe_add(x_j, x_k), D)), D
                    ),
                    ANN,
                ),
                27,
            ),
            convert(A_MULTIPLIER, int256),
        ),
    )
    d: int256 = unsafe_div(unsafe_add(10**18, gamma)**2, 27)

    d0: int256 = abs(
        unsafe_sub(unsafe_div(unsafe_mul(unsafe_mul(3, a), c), b), b)
    )
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
        additional_prec = abs(a) / abs(b)
        a = unsafe_div(unsafe_mul(a, additional_prec), divider)
        b = unsafe_div(unsafe_mul(b, additional_prec), divider)
        c = unsafe_div(unsafe_mul(c, additional_prec), divider)
        d = unsafe_div(unsafe_mul(d, additional_prec), divider)
    else:
        additional_prec = abs(b) / abs(a)
        a = unsafe_div(unsafe_div(a, additional_prec), divider)
        b = unsafe_div(unsafe_div(b, additional_prec), divider)
        c = unsafe_div(unsafe_div(c, additional_prec), divider)
        d = unsafe_div(unsafe_div(d, additional_prec), divider)

    delta0: int256 = unsafe_sub(
        unsafe_div(unsafe_mul(unsafe_mul(3, a), c), b), b
    )
    delta1: int256 = unsafe_sub(
        unsafe_sub(
            unsafe_div(unsafe_mul(unsafe_mul(9, a), c), b), unsafe_mul(2, b)
        ),
        unsafe_div(unsafe_mul(unsafe_div(unsafe_mul(27, a**2), b), d), b),
    )

    sqrt_arg: int256 = unsafe_add(
        delta1**2,
        unsafe_mul(unsafe_div(unsafe_mul(4, delta0**2), b), delta0),
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
        second_cbrt = convert(
            self._cbrt(
                unsafe_div(convert((unsafe_add(delta1, sqrt_val)), uint256), 2)
            ),
            int256,
        )
    else:
        second_cbrt = -convert(
            self._cbrt(
                unsafe_div(convert(-unsafe_sub(delta1, sqrt_val), uint256), 2)
            ),
            int256,
        )

    C1: int256 = unsafe_div(
        unsafe_mul(unsafe_div(b_cbrt**2, 10**18), second_cbrt), 10**18
    )

    root_K0: int256 = unsafe_div(
        unsafe_sub(unsafe_add(b, unsafe_div(unsafe_mul(b, delta0), C1)), C1), 3
    )
    root: uint256 = convert(
        unsafe_div(
            unsafe_mul(
                unsafe_div(
                    unsafe_mul(unsafe_div(unsafe_div(D**2, 27), x_k), D), x_j
                ),
                root_K0,
            ),
            a,
        ),
        uint256,
    )

    return [
        root, convert(unsafe_div(unsafe_mul(10**18, root_K0), a), uint256)
    ]


@internal
@view
def _newton_y(
    ANN: uint256, gamma: uint256, x: uint256[N_COINS], D: uint256, i: uint256
) -> uint256:

    # Safety checks
    assert ANN > MIN_A - 1 and ANN < MAX_A + 1, "dev: unsafe values A"
    assert (
        gamma > MIN_GAMMA - 1 and gamma < MAX_GAMMA + 1
    ), "dev: unsafe values gamma"
    assert (
        D > 10**17 - 1 and D < 10**15 * 10**18 + 1
    ), "dev: unsafe values D"

    for k in range(3):
        if k != i:
            frac: uint256 = x[k] * 10**18 / D
            assert (
                frac > 10**16 - 1 and frac < 10**20 + 1
            ), "dev: unsafe values x[i]"
    y: uint256 = D / N_COINS
    K0_i: uint256 = 10**18
    S_i: uint256 = 0

    x_sorted: uint256[N_COINS] = x
    x_sorted[i] = 0
    x_sorted = self._sort(x_sorted)  # From high to low

    convergence_limit: uint256 = max(
        max(x_sorted[0] / 10**14, D / 10**14), 100
    )
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
        # y = (yfprime + 10**18 * D - 10**18 * S) // fprime + mul1 // fprime * (10**18 - K0) // K0
        y_minus = mul1 / fprime
        y_plus = (
            yfprime + 10**18 * D
        ) / fprime + y_minus * 10**18 / K0
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
            frac: uint256 = y * 10**18 / D
            assert (frac > 10**16 - 1) and (frac < 10**20 + 1), "dev: unsafe value for y"
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
    @param ANN: the A * N**N value
    @param gamma: the gamma value
    @param x_unsorted: the array of coin balances (not sorted)
    @param K0_prev: apriori for newton's method derived from get_y_int. Defaults
                    to zero (no apriori)
    @return the invariant
    """
    x: uint256[N_COINS] = self._sort(x_unsorted)
    assert x[0] < max_value(uint256) / 10**18 * N_COINS**N_COINS, "dev: out of limits"

    S: uint256 = 0
    for x_i in x:
        S += x_i

    D: uint256 = 0
    if K0_prev == 0:
        D = N_COINS * self._geometric_mean(x, False)
    else:
        if S > 10**36:
            D = self._cbrt(
                unsafe_mul(
                    unsafe_mul(
                        unsafe_div(
                            unsafe_mul(
                                unsafe_div(unsafe_mul(x[0], x[1]), 10**36),
                                x[2],
                            ),
                            K0_prev,
                        ),
                        27,
                    ),
                    10**12,
                )
            )
        elif S > 10**24:
            D = self._cbrt(
                unsafe_mul(
                    unsafe_mul(
                        unsafe_div(
                            unsafe_mul(
                                unsafe_div(unsafe_mul(x[0], x[1]), 10**24),
                                x[2],
                            ),
                            K0_prev,
                        ),
                        27,
                    ),
                    10**6,
                )
            )
        else:
            D = self._cbrt(
                unsafe_mul(
                    unsafe_div(
                        unsafe_mul(
                            unsafe_div(unsafe_mul(x[0], x[1]), 10**18), x[2]
                        ),
                        K0_prev,
                    ),
                    27,
                )
            )

    # initialise variables:
    diff: uint256 = 0
    K0: uint256 = 0
    _g1k0: uint256 = 0
    mul1: uint256 = 0
    mul2: uint256 = 0
    neg_fprime: uint256 = 0
    D_plus: uint256 = 0
    D_minus: uint256 = 0

    for i in range(255):
        D_prev: uint256 = D

        # 10**18 * x[0] * N_COINS / D * x[1] * N_COINS / D * x[2] * N_COINS / D
        # one safediv so D = 0 is handled.
        K0 = unsafe_div(
            unsafe_mul(
                unsafe_mul(
                    unsafe_div(
                        unsafe_mul(
                            unsafe_mul(
                                unsafe_mul(unsafe_mul(10**18, x[0]), N_COINS) / D,
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
        )

        _g1k0 = gamma + 10**18
        if _g1k0 > K0:
            _g1k0 = _g1k0 - K0 + 1
        else:
            _g1k0 = K0 - _g1k0 + 1


        # D / (A * N**N) * _g1k0**2 / gamma**2
        # 10**18 * D / gamma * _g1k0 / gamma * _g1k0 * A_MULTIPLIER / ANN
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
        )

        # 2*N*K0 / _g1k0
        # (2 * 10**18) * N_COINS * K0 / _g1k0
        mul2 = unsafe_div(
            unsafe_mul(unsafe_mul(2 * 10**18, N_COINS), K0), _g1k0
        )

        # neg_fprime: uint256 = (S + S * mul2 / 10**18) + mul1 * N_COINS / K0 - mul2 * D / 10**18
        neg_fprime = unsafe_sub(
            unsafe_add(
                unsafe_add(S, unsafe_div(unsafe_mul(S, mul2), 10**18)),
                unsafe_div(unsafe_mul(mul1, N_COINS), K0),
            ),
            unsafe_div(unsafe_mul(mul2, D), 10**18),
        )

        # D -= f / fprime
        # D * (neg_fprime + S) / neg_fprime
        D_plus = unsafe_div(
            unsafe_mul(D, unsafe_add(neg_fprime, S)), neg_fprime
        )
        # D*D / neg_fprime
        D_minus = unsafe_div(unsafe_mul(D, D), neg_fprime)
        if 10**18 > K0:
            # D_minus += D * (mul1 / neg_fprime) / 10**18 * (10**18 - K0) / K0
            D_minus += unsafe_div(
                unsafe_mul(
                    unsafe_div(
                        unsafe_mul(D, unsafe_div(mul1, neg_fprime)), 10**18
                    ),
                    unsafe_sub(10**18, K0),
                ),
                K0,
            )
        else:
            # D_minus -= D * (mul1 / neg_fprime) / 10**18 * (K0 - 10**18) / K0
            D_minus -= unsafe_div(
                unsafe_mul(
                    unsafe_div(
                        unsafe_mul(D, unsafe_div(mul1, neg_fprime)), 10**18
                    ),
                    unsafe_sub(K0, 10**18),
                ),
                K0,
            )

        if D_plus > D_minus:
            D = unsafe_sub(D_plus, D_minus)
        else:
            D = unsafe_div(unsafe_sub(D_minus, D_plus), 2)

        if D > D_prev:
            diff = unsafe_sub(D, D_prev)
        else:
            diff = unsafe_sub(D_prev, D)

        # Could reduce precision for gas efficiency here:
        if unsafe_mul(diff, 10**14) < max(10**16, D):

            # Test that we are safe with the next newton_y
            for _x in x:
                frac: uint256 = unsafe_div(unsafe_mul(_x, 10**18), D)
                assert (frac > 10**16 - 1) and (frac < 10**20 + 1)  # dev: unsafe values x[i]

            return D

    raise "Did not converge"


@external
@view
def get_dydx():
    # TODO: implement dy/dx
    pass


# --------------------------- Math Utils -------------------------------------


@external
@view
def cbrt(x: uint256) -> uint256:
    return self._cbrt(x)


@external
@view
def geometric_mean(unsorted_x: uint256[N_COINS], sort: bool = True) -> uint256:
    return self._geometric_mean(unsorted_x, sort)


@external
@view
def reduction_coefficient(x: uint256[N_COINS], fee_gamma: uint256) -> uint256:
    return self._reduction_coefficient(x, fee_gamma)


@external
@view
def wad_exp(_power: int256) -> uint256:
    return self._exp(_power)


@internal
@pure
def _reduction_coefficient(x: uint256[N_COINS], fee_gamma: uint256) -> uint256:
    """
    fee_gamma / (fee_gamma + (1 - K))
    where
    K = prod(x) / (sum(x) / N)**N
    (all normalized to 1e18)
    """
    K: uint256 = 10**18
    S: uint256 = x[0]
    S = unsafe_add(S, x[1])
    S = unsafe_add(S, x[2])

    # Could be good to pre-sort x, but it is used only for dynamic fee,
    # so that is not so important
    K = unsafe_div(unsafe_mul(unsafe_mul(K, N_COINS), x[0]), S)
    K = unsafe_div(unsafe_mul(unsafe_mul(K, N_COINS), x[1]), S)
    K = unsafe_div(unsafe_mul(unsafe_mul(K, N_COINS), x[2]), S)

    if fee_gamma > 0:
        K = unsafe_mul(fee_gamma, 10**18) / unsafe_sub(
            unsafe_add(fee_gamma, 10**18), K
        )

    return K


@internal
@pure
def _exp(_power: int256) -> uint256:
    """
    @notice Calculates the e**x with 1e18 precision
    @param _power The number to calculate the exponential of
    @return The exponential of the given number
    """

    # This implementation is borrowed from efforts from transmissions11 and Remco Bloemen:
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
    p = unsafe_add(unsafe_div(unsafe_mul(p, y), 2**96), 28719021644029726153956944680412240)
    p = unsafe_add(unsafe_mul(p, x), (4385272521454847904659076985693276 * 2**96))

    q: int256 = x - 2855989394907223263936484059900
    q = unsafe_add(unsafe_div(unsafe_mul(q, x), 2**96), 50020603652535783019961831881945)
    q = unsafe_sub(unsafe_div(unsafe_mul(q, x), 2**96), 533845033583426703283633433725380)
    q = unsafe_add(unsafe_div(unsafe_mul(q, x), 2**96), 3604857256930695427073651918091429)
    q = unsafe_sub(unsafe_div(unsafe_mul(q, x), 2**96), 14423608567350463180887372962807573)
    q = unsafe_add(unsafe_div(unsafe_mul(q, x), 2**96), 26449188498355588339934803723976023)

    return shift(
        unsafe_mul(convert(unsafe_div(p, q), uint256), 3822833074963236453042738258902158003155416615667),
        unsafe_sub(k, 195),
    )


@internal
@pure
def _log2(x: uint256) -> int256:
    """
    @notice Compute the binary logarithm of `x`
    @param x The number to compute the logarithm of
    @return The binary logarithm of `x`
    """
    # This was inspired from Stanford's 'Bit Twiddling Hacks' by Sean Eron Anderson:
    # https://graphics.stanford.edu/~seander/bithacks.html#IntegerLog
    #
    # More inspiration was derived from:
    # https://github.com/transmissions11/solmate/blob/main/src/utils/SignedWadMath.sol

    log2x: int256 = 0
    if x > 340282366920938463463374607431768211455:
        log2x = 128
    if unsafe_div(x, shift(2, log2x)) > 18446744073709551615:
        log2x = log2x | 64
    if unsafe_div(x, shift(2, log2x)) > 4294967295:
        log2x = log2x | 32
    if unsafe_div(x, shift(2, log2x)) > 65535:
        log2x = log2x | 16
    if unsafe_div(x, shift(2, log2x)) > 255:
        log2x = log2x | 8
    if unsafe_div(x, shift(2, log2x)) > 15:
        log2x = log2x | 4
    if unsafe_div(x, shift(2, log2x)) > 3:
        log2x = log2x | 2
    if unsafe_div(x, shift(2, log2x)) > 1:
        log2x = log2x | 1

    return log2x


@internal
@pure
def _cbrt(x: uint256) -> uint256:
    """
    @notice Calculate the cubic root of a number in 1e18 precision
    @dev Consumes around 1500 gas units
    @param x The number to calculate the cubic root of
    @return The cubic root of the number
    """

    xx: uint256 = 0
    if x >= 115792089237316195423570985008687907853269 * 10**18:
        xx = x
    elif x >= 115792089237316195423570985008687907853269:
        xx = unsafe_mul(x, 10**18)
    else:
        xx = unsafe_mul(x, 10**36)

    log2x: int256 = self._log2(xx)

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
        return a * 10**12
    elif x >= 115792089237316195423570985008687907853269:
        return a * 10**6

    return a


@internal
@pure
def _sort(unsorted_x: uint256[N_COINS]) -> uint256[N_COINS]:
    """
    @notice Sorts the array of 3 numbers in descending order
    @param unsorted_x The array to sort
    @return The sorted array
    """
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
def _geometric_mean(_x: uint256[3], sort: bool = True) -> uint256:
    x: uint256[N_COINS] = _x
    if sort:
        x = self._sort(_x)

    prod: uint256 = x[0] * x[1] / 10**18 * x[2] / 10**18
    assert prod > 0

    return self._cbrt(prod)
