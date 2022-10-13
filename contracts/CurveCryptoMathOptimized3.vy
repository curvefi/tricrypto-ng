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
def cbrt(x: uint256) -> uint256:
    """
    @notice Calculate the cubic root of a number in 1e18 precision
    @param x The number to calculate the cubic root of
    @return The cubic root of the number
    """

    # We artificially set a cap to the values for which we can compute the
    # cube roots safely. This is not to say that there are no values above
    # max(uint256) // 10**36 for which we cannot get good cube root estimates.
    # Beyond this point, accuracy is not guaranteed as overflows start to occur:
    assert x < 115792089237316195423570985008687907853269, "inaccurate cbrt"

    # We multiply the input `x` by 10 ** 36 to increase the precision of the
    # calculated cube root, such that: cbrt(10**18) = 10**18, cbrt(1) = 10**12
    x_squared: uint256 = unsafe_mul(x, 10**36)

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
    if x_squared > 340282366920938463463374607431768211455:
        log2x = 128
    if unsafe_div(x_squared, shift(2, log2x)) > 18446744073709551615:
        log2x = log2x | 64
    if unsafe_div(x_squared, shift(2, log2x)) > 4294967295:
        log2x = log2x | 32
    if unsafe_div(x_squared, shift(2, log2x)) > 65535:
        log2x = log2x | 16
    if unsafe_div(x_squared, shift(2, log2x)) > 255:
        log2x = log2x | 8
    if unsafe_div(x_squared, shift(2, log2x)) > 15:
        log2x = log2x | 4
    if unsafe_div(x_squared, shift(2, log2x)) > 3:
        log2x = log2x | 2
    if unsafe_div(x_squared, shift(2, log2x)) > 1:
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
    cbrt_x: uint256 = unsafe_div(
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
    cbrt_x = unsafe_div(unsafe_add(unsafe_mul(2, cbrt_x), unsafe_div(x_squared, unsafe_mul(cbrt_x, cbrt_x))), 3)
    cbrt_x = unsafe_div(unsafe_add(unsafe_mul(2, cbrt_x), unsafe_div(x_squared, unsafe_mul(cbrt_x, cbrt_x))), 3)
    cbrt_x = unsafe_div(unsafe_add(unsafe_mul(2, cbrt_x), unsafe_div(x_squared, unsafe_mul(cbrt_x, cbrt_x))), 3)
    cbrt_x = unsafe_div(unsafe_add(unsafe_mul(2, cbrt_x), unsafe_div(x_squared, unsafe_mul(cbrt_x, cbrt_x))), 3)
    cbrt_x = unsafe_div(unsafe_add(unsafe_mul(2, cbrt_x), unsafe_div(x_squared, unsafe_mul(cbrt_x, cbrt_x))), 3)
    cbrt_x = unsafe_div(unsafe_add(unsafe_mul(2, cbrt_x), unsafe_div(x_squared, unsafe_mul(cbrt_x, cbrt_x))), 3)
    cbrt_x = unsafe_div(unsafe_add(unsafe_mul(2, cbrt_x), unsafe_div(x_squared, unsafe_mul(cbrt_x, cbrt_x))), 3)

    return cbrt_x


@internal
@pure
def exp(_power: int256) -> uint256:

    if _power <= -42139678854452767551:
        return 0

    if _power >= 135305999368893231589:
        raise "exp overflow"

    x: int256 = unsafe_div(unsafe_mul(_power, 2**96), 10**18)

    k: int256 = unsafe_div(
        unsafe_add(
            unsafe_div(unsafe_mul(x, 2**96), 54916777467707473351141471128),
            2**95
        ),
        2**96
    )
    x = unsafe_sub(x, unsafe_mul(k, 54916777467707473351141471128))

    y: int256 = unsafe_add(x, 1346386616545796478920950773328)
    y = unsafe_add(unsafe_div(unsafe_mul(y, x), 2**96), 57155421227552351082224309758442)
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
        unsafe_sub(k, 195))


# --- External maff functions ---


# TODO: the following method should use cbrt:
@external
@view
def geometric_mean(unsorted_x: uint256[3], sort: bool = True) -> uint256:
    """
    @notice calculates geometric of 3 element arrays: cbrt(x[0] * x[1] * x[2])
    @dev This approach is specifically optimised for 3 element arrays. To
         use it for 2 element arrays, consider using the vyper builtin: isqrt.
    @param unsorted_x: array of 3 uint256 values
    @param sort: if True, the array will be sorted before calculating the mean
    @return the geometric mean of the array
    """
    x: uint256[3] = unsorted_x

    # cheap sort using temp var: only works if N_COINS == 3
    if sort:
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

    # geometric mean calculation:
    return self.cbrt(x[0] * x[1] * x[2])


@external
@view
def halfpow(power: uint256) -> uint256:
    """
    1e18 * 0.5 ** (power/1e18)

    Inspired by: https://github.com/transmissions11/solmate/blob/4933263adeb62ee8878028e542453c4d1a071be9/src/utils/FixedPointMathLib.sol#L34

    This should cost about 1k gas
    """

    # TODO: borrowed from unoptimised halfpow, please check the following:
    if unsafe_div(power, 10**18) > 59:
        return 0

    # exp(-ln(2) * x) = 0.5 ** x. so, get -ln(2) * x:
    return self.exp(-1 * 693147180559945344 * convert(power, int256) / 10 ** 18)


@external
@view
def get_D(ANN: uint256, gamma: uint256, x_unsorted: uint256[N_COINS]) -> uint256:
    """
    Finding the invariant analytically.
    ANN is higher by the factor A_MULTIPLIER
    ANN is already A * N**N
    """
    #TODO: add tricrypto math optimisations here
    return ANN


@external
@view
def get_y(ANN: uint256, gamma: uint256, x: uint256[N_COINS], D: uint256, i: uint256) -> uint256:
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

    a: uint256 = 10**28/27
    b: uint256 = 10**28/9 + 2*10**10*gamma/27 - D**2/x[j]*gamma**2/x[k]*ANN/27**2/10**8/A_MULTIPLIER
    c: uint256 = 0
    if D > x[j] + x[k]:
        c = 10**28/9 + gamma*(gamma + 4*10**18)/27/10**8 - gamma**2*(D-x[j]-x[k])/D*ANN/10**8/27/A_MULTIPLIER
    else:
        c = 10**28/9 + gamma*(gamma + 4*10**18)/27/10**8 + gamma**2*(x[j]+x[k]-D)/D*ANN/10**8/27/A_MULTIPLIER
    d: uint256 = (10**18 + gamma)**2/10**8/27

    delta0: uint256 = 3*a*c/b - b
    delta1: uint256 = 9*a*c/b - 2*b - 27*a**2/b*d/b

    C1: uint256 = self.cbrt(b*(delta1 + isqrt(delta1**2 + 4*delta0**3/b))/2/10**18*b/10**18)
    root_K0: uint256 = (10**18*b - 10**18*C1 + 10**18*b*delta0/C1)/(3*a)

    return root_K0*D/x[j]*D/x[k]*D/27/10**18
