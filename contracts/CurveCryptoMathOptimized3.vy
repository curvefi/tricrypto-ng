# @version 0.3.7
# (c) Curve.Fi, 2022
# Math for 3-coin Curve cryptoswap pools


N_COINS: constant(uint256) = 3
A_MULTIPLIER: constant(uint256) = 10000

MIN_GAMMA: constant(uint256) = 10**10
MAX_GAMMA: constant(uint256) = 5 * 10**16

MIN_A: constant(uint256) = N_COINS**N_COINS * A_MULTIPLIER / 100
MAX_A: constant(uint256) = N_COINS**N_COINS * A_MULTIPLIER * 1000


# --- Internal maff ---

@internal
@pure
def sort(A0: uint256[N_COINS]) -> uint256[N_COINS]:
    """
    Insertion sort from high to low
    """
    A: uint256[N_COINS] = A0
    for i in range(1, N_COINS):
        x: uint256 = A[i]
        cur: uint256 = i
        for j in range(N_COINS):
            y: uint256 = A[cur-1]
            if y > x:
                break
            A[cur] = y
            cur -= 1
            if cur == 0:
                break
        A[cur] = x
    return A


@internal
@pure
def cbrt(x: uint256) -> uint256:
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

    # ---- CALCULATE INITIAL GUESS FOR CUBE ROOT ---- #
    # We can guess the cube root of `x` using cheap integer operations. The guess
    # is calculated as follows:
    #    y = cbrt(a)
    # => y = cbrt(2**log2(a)) # <-- substituting `a = 2 ** log2(a)`
    # => y = 2**(log2(a) / 3) ≈ 2**|log2(a)/3|

    # Calculate log2(x). The following is inspire from:
    #
    # This was inspired from Stanford's 'Bit Twiddling Hacks' by Sean Eron Anderson:
    # https://graphics.stanford.edu/~seander/bithacks.html#IntegerLog
    #
    # More inspiration was derived from:
    # https://github.com/transmissions11/solmate/blob/main/src/utils/SignedWadMath.sol

    log2x: int256 = 0
    if xx > 340282366920938463463374607431768211455:
        log2x = 128
    if unsafe_div(xx, shift(2, log2x)) > 18446744073709551615:
        log2x = log2x | 64
    if unsafe_div(xx, shift(2, log2x)) > 4294967295:
        log2x = log2x | 32
    if unsafe_div(xx, shift(2, log2x)) > 65535:
        log2x = log2x | 16
    if unsafe_div(xx, shift(2, log2x)) > 255:
        log2x = log2x | 8
    if unsafe_div(xx, shift(2, log2x)) > 15:
        log2x = log2x | 4
    if unsafe_div(xx, shift(2, log2x)) > 3:
        log2x = log2x | 2
    if unsafe_div(xx, shift(2, log2x)) > 1:
        log2x = log2x | 1

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
            pow_mod256(
                2,
                unsafe_div(
                    convert(log2x, uint256), 3  # <- pow
                )
            ),
            pow_mod256(1260, remainder)
        ),
        pow_mod256(1000, remainder)
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
        return a*10**12
    elif x >= 115792089237316195423570985008687907853269:
        return a*10**6

    return a


@internal
@pure
def exp(_power: int256) -> uint256:
    """
    @notice Calculates the e**x with 1e18 precision
    @param _power The number to calculate the exponential of
    @return The exponential of the given number
    """

    # This implementation is borrowed from efforts from transmissions11 and Remco Bloemen:
    # https://github.com/transmissions11/solmate/blob/main/src/utils/SignedWadMath.sol
    # Method: wadExp

    # For exp(_power) < 0.5, wadExp returns 0. This is the case for:
    # _power <= floor(log(0.5e18) * 1e18) ~ -42e18
    if _power <= -42139678854452767551:
        return 0

    # for exp(_power) > (2**255 - 1) / 1e18, wadExp will overflow. So, set a cap to
    # _power here:
    if _power >= 135305999368893231589:
        raise "exp overflow"

    # If the above two conditions are satisfied, _power ∈ (-42e18, 135e18). Conversion
    # to binary basis and increasing precision involves dividing by 10**18 and multiplying
    # by 2**96 (calculations in binary basis is cheaper than 1e18 basis). So 256 - 96 = 160
    # bits is the whole number part, and 96 bits is the fractional part:
    x: int256 = unsafe_div(unsafe_mul(_power, 2**96), 10**18)

    # Explanation borrowed from solmate:
    # Reduce range of x to (-½ ln 2, ½ ln 2) * 2**96 by factoring out powers
    # of two such that exp(x) = exp(x') * 2**k, where k is an integer.
    # Solving this gives k = round(x / log(2)) and x' = x - k * log(2).
    # k ∈ [-61, 195].
    k: int256 = unsafe_div(
        unsafe_add(
            unsafe_div(unsafe_mul(x, 2**96), 54916777467707473351141471128),
            2**95
        ),
        2**96
    )
    x = unsafe_sub(x, unsafe_mul(k, 54916777467707473351141471128))

    # Explanation borrowed from solmate:
    # Evaluate using a (6, 7)-term rational approximation.
    # p is made monic, we'll multiply by a scale factor later.
    y: int256 = unsafe_add(x, 1346386616545796478920950773328)
    y = unsafe_add(unsafe_div(unsafe_mul(y, x), 2**96), 57155421227552351082224309758442)
    p: int256 = unsafe_sub(unsafe_add(y, x), 94201549194550492254356042504812)
    p = unsafe_add(unsafe_div(unsafe_mul(p, y), 2**96), 28719021644029726153956944680412240)
    p = unsafe_add(unsafe_mul(p, x), (4385272521454847904659076985693276 * 2**96))

    # Explanation borrowed from solmate:
    # We leave p in 2**192 basis so we don't need to scale it back up for the division.
    q: int256 = x - 2855989394907223263936484059900
    q = unsafe_add(unsafe_div(unsafe_mul(q, x), 2**96), 50020603652535783019961831881945)
    q = unsafe_sub(unsafe_div(unsafe_mul(q, x), 2**96), 533845033583426703283633433725380)
    q = unsafe_add(unsafe_div(unsafe_mul(q, x), 2**96), 3604857256930695427073651918091429)
    q = unsafe_sub(unsafe_div(unsafe_mul(q, x), 2**96), 14423608567350463180887372962807573)
    q = unsafe_add(unsafe_div(unsafe_mul(q, x), 2**96), 26449188498355588339934803723976023)

    # Explanation borrowed from solmate:
    # r = unsafe_div(p, q)
    # We now need to multiply r by:
    # * the scale factor s = ~6.031367120.
    # * the 2**k factor from the range reduction.
    # * the 1e18 / 2**96 factor for base conversion.
    return shift(
        unsafe_mul(convert(unsafe_div(p, q), uint256), 3822833074963236453042738258902158003155416615667),
        unsafe_sub(k, 195))


@internal
@view
def _geometric_mean(unsorted_x: uint256[N_COINS], sort: bool = True) -> uint256:
    """
    (x[0] * x[1] * ...) ** (1/N)
    """
    x: uint256[N_COINS] = unsorted_x
    if sort:
        x = self.sort(x)
    D: uint256 = x[0]
    diff: uint256 = 0
    for i in range(255):
        D_prev: uint256 = D
        tmp: uint256 = 10**18
        for _x in x:
            tmp = tmp * _x / D
        D = D * ((N_COINS - 1) * 10**18 + tmp) / (N_COINS * 10**18)
        if D > D_prev:
            diff = D - D_prev
        else:
            diff = D_prev - D
        if diff <= 1 or diff * 10**18 < D:
            return D
    raise "Did not converge"


# --- External maff functions ---


@external
@view
def geometric_mean(unsorted_x: uint256[N_COINS], sort: bool = True) -> uint256:
    return self._geometric_mean(unsorted_x, sort)


@external
@view
def reduction_coefficient(x: uint256[N_COINS], fee_gamma: uint256) -> uint256:
    """
    fee_gamma / (fee_gamma + (1 - K))
    where
    K = prod(x) / (sum(x) / N)**N
    (all normalized to 1e18)
    """
    # TODO: optimise add tests
    K: uint256 = 10**18
    S: uint256 = 0
    for x_i in x:
        S += x_i
    # Could be good to pre-sort x, but it is used only for dynamic fee,
    # so that is not so important
    for x_i in x:
        K = K * N_COINS * x_i / S
    if fee_gamma > 0:
        K = fee_gamma * 10**18 / (fee_gamma + 10**18 - K)
    return K


@external
@view
def halfpow(power: uint256) -> uint256:
    """
    @notice halfpow(power) = 1e18 * 0.5 ** (power/1e18)
    @param power: the exponent to raise e by
    @return the result of 1e18 * 0.5 ** (power/1e18)
    """
    # TODO: borrowed from unoptimised halfpow, please check the following:
    if unsafe_div(power, 10**18) > 59:
        return 0

    # exp(-ln(2) * x) = 0.5 ** x. so, get -ln(2) * x:
    return self.exp(-1 * 693147180559945344 * convert(power, int256) / 10 ** 18)


@external
@view
def newton_D(ANN: uint256, gamma: uint256, x_unsorted: uint256[N_COINS]) -> uint256:
    """
    @notice Finding the invariant via newtons method using good initial guesses.
    @dev ANN is higher by the factor A_MULTIPLIER
    @dev ANN is already A * N**N
    @param ANN: the A * N**N value
    @param gamma: the gamma value
    @param x_unsorted: the array of coin balances (not sorted)
    @return the invariant
    """
    #TODO: add tricrypto math optimisations here

    # Safety checks
    assert ANN > MIN_A - 1 and ANN < MAX_A + 1  # dev: unsafe values A
    assert gamma > MIN_GAMMA - 1 and gamma < MAX_GAMMA + 1  # dev: unsafe values gamma

    # Initial value of invariant D is that for constant-product invariant
    x: uint256[N_COINS] = self.sort(x_unsorted)

    assert x[0] > 10**9 - 1 and x[0] < 10**15 * 10**18 + 1  # dev: unsafe values x[0]
    assert x[1] * 10**18 / x[0] > 10**11-1  # dev: unsafe values x[1]
    assert x[2] * 10**18 / x[0] > 10**11-1  # dev: unsafe values x[2]

    D: uint256 = N_COINS * self._geometric_mean(x, False)
    S: uint256 = 0
    for x_i in x:
        S += x_i

    for i in range(255):
        D_prev: uint256 = D

        K0: uint256 = 10**18
        for _x in x:
            K0 = K0 * _x * N_COINS / D

        _g1k0: uint256 = gamma + 10**18
        if _g1k0 > K0:
            _g1k0 = _g1k0 - K0 + 1
        else:
            _g1k0 = K0 - _g1k0 + 1

        # D / (A * N**N) * _g1k0**2 / gamma**2
        mul1: uint256 = 10**18 * D / gamma * _g1k0 / gamma * _g1k0 * A_MULTIPLIER / ANN

        # 2*N*K0 / _g1k0
        mul2: uint256 = (2 * 10**18) * N_COINS * K0 / _g1k0

        neg_fprime: uint256 = (S + S * mul2 / 10**18) + mul1 * N_COINS / K0 - mul2 * D / 10**18

        # D -= f / fprime
        D_plus: uint256 = D * (neg_fprime + S) / neg_fprime
        D_minus: uint256 = D*D / neg_fprime
        if 10**18 > K0:
            D_minus += D * (mul1 / neg_fprime) / 10**18 * (10**18 - K0) / K0
        else:
            D_minus -= D * (mul1 / neg_fprime) / 10**18 * (K0 - 10**18) / K0

        if D_plus > D_minus:
            D = D_plus - D_minus
        else:
            D = (D_minus - D_plus) / 2

        diff: uint256 = 0
        if D > D_prev:
            diff = D - D_prev
        else:
            diff = D_prev - D
        if diff * 10**14 < max(10**16, D):  # Could reduce precision for gas efficiency here
            # Test that we are safe with the next newton_y
            for _x in x:
                frac: uint256 = _x * 10**18 / D
                assert (frac > 10**16 - 1) and (frac < 10**20 + 1)  # dev: unsafe values x[i]
            return D

    raise "Did not converge"


@external
@view
def newton_y(ANN: uint256, gamma: uint256, x: uint256[N_COINS], D: uint256, i: uint256) -> uint256:
    """
    Calculating x[i] given other balances x[0..N_COINS-1] and invariant D
    ANN = A * N**N
    """
    # Safety checks
    assert ANN > MIN_A - 1 and ANN < MAX_A + 1  # dev: unsafe values A
    assert gamma > MIN_GAMMA - 1 and gamma < MAX_GAMMA + 1  # dev: unsafe values gamma
    assert D > 10**17 - 1 and D < 10**15 * 10**18 + 1 # dev: unsafe values D
    for k in range(3):
        if k != i:
            frac: uint256 = x[k] * 10**18 / D
            assert (frac > 10**16 - 1) and (frac < 10**20 + 1)  # dev: unsafe values x[i]

    y: uint256 = D / N_COINS
    K0_i: uint256 = 10**18
    S_i: uint256 = 0

    x_sorted: uint256[N_COINS] = x
    x_sorted[i] = 0
    x_sorted = self.sort(x_sorted)  # From high to low

    convergence_limit: uint256 = max(max(x_sorted[0] / 10**14, D / 10**14), 100)
    for j in range(2, N_COINS+1):
        _x: uint256 = x_sorted[N_COINS-j]
        y = y * D / (_x * N_COINS)  # Small _x first
        S_i += _x
    for j in range(N_COINS-1):
        K0_i = K0_i * x_sorted[j] * N_COINS / D  # Large _x first

    for j in range(255):
        y_prev: uint256 = y

        K0: uint256 = K0_i * y * N_COINS / D
        S: uint256 = S_i + y

        _g1k0: uint256 = gamma + 10**18
        if _g1k0 > K0:
            _g1k0 = _g1k0 - K0 + 1
        else:
            _g1k0 = K0 - _g1k0 + 1

        # D / (A * N**N) * _g1k0**2 / gamma**2
        mul1: uint256 = 10**18 * D / gamma * _g1k0 / gamma * _g1k0 * A_MULTIPLIER / ANN

        # 2*K0 / _g1k0
        mul2: uint256 = 10**18 + (2 * 10**18) * K0 / _g1k0

        yfprime: uint256 = 10**18 * y + S * mul2 + mul1
        _dyfprime: uint256 = D * mul2
        if yfprime < _dyfprime:
            y = y_prev / 2
            continue
        else:
            yfprime -= _dyfprime
        fprime: uint256 = yfprime / y

        # y -= f / f_prime;  y = (y * fprime - f) / fprime
        # y = (yfprime + 10**18 * D - 10**18 * S) // fprime + mul1 // fprime * (10**18 - K0) // K0
        y_minus: uint256 = mul1 / fprime
        y_plus: uint256 = (yfprime + 10**18 * D) / fprime + y_minus * 10**18 / K0
        y_minus += 10**18 * S / fprime

        if y_plus < y_minus:
            y = y_prev / 2
        else:
            y = y_plus - y_minus

        diff: uint256 = 0
        if y > y_prev:
            diff = y - y_prev
        else:
            diff = y_prev - y
        if diff < max(convergence_limit, y / 10**14):
            frac: uint256 = y * 10**18 / D
            assert (frac > 10**16 - 1) and (frac < 10**20 + 1)  # dev: unsafe value for y
            return y

    raise "Did not converge"
