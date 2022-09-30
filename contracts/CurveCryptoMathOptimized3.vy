# @version 0.3.7
# (c) Curve.Fi, 2022
# Math for USDT/BTC/ETH pool


N_COINS: constant(uint256) = 3  # <- change
A_MULTIPLIER: constant(uint256) = 10000

MIN_GAMMA: constant(uint256) = 10**10
MAX_GAMMA: constant(uint256) = 5 * 10**16

MIN_A: constant(uint256) = N_COINS**N_COINS * A_MULTIPLIER / 100
MAX_A: constant(uint256) = N_COINS**N_COINS * A_MULTIPLIER * 1000


# --- Internal maff ---

# TODO: check if this can be made more efficient since we're only
# sorting three numbers here:
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

    # we artificially set a cap to the values for which we can compute the
    # cube roots safely. This is not to say that there are no values above
    # 10**59 for which we cannot get good cube root estimates. However,
    # beyond this point, accuracy is not guaranteed.
    assert x < 10**59, "inaccurate cbrt"

    # multiply with 10 ** 18 for increasing cbrt precision
    _x: uint256 = unsafe_mul(x, 10**18)

    # get log2(x) for approximating initial value
    # logic is: cbrt(a) = cbrt(2**(log2(a))) = 2**(log2(a) / 3) ≈ 2**|log2(a)/3|
    # from: https://github.com/transmissions11/solmate/blob/b9d69da49bbbfd090f1a73a4dba28aa2d5ee199f/src/utils/FixedPointMathLib.sol#L352

    a_pow: int256 = 0
    if _x > 340282366920938463463374607431768211455:
        a_pow = 128
    if unsafe_div(_x, shift(2, a_pow)) > 18446744073709551615:
        a_pow = a_pow | 64
    if unsafe_div(_x, shift(2, a_pow)) > 4294967295:
        a_pow = a_pow | 32
    if unsafe_div(_x, shift(2, a_pow)) > 65535:
        a_pow = a_pow | 16
    if unsafe_div(_x, shift(2, a_pow)) > 255:
        a_pow = a_pow | 8
    if unsafe_div(_x, shift(2, a_pow)) > 15:
        a_pow = a_pow | 4
    if unsafe_div(_x, shift(2, a_pow)) > 3:
        a_pow = a_pow | 2
    if unsafe_div(_x, shift(2, a_pow)) > 1:
        a_pow = a_pow | 1

    # initial value: 2**|log2(a)/3|
    # which is: 2 ** (n / 3) * 1260 ** (n % 3) / 1000 ** (n % 3)
    a_pow_mod: uint256 = convert(a_pow, uint256) % 3
    a: uint256 = unsafe_div(
        unsafe_mul(
            pow_mod256(
                2,
                unsafe_div(
                    convert(a_pow, uint256), 3
                )
            ),
            pow_mod256(1260, a_pow_mod)
        ),
        pow_mod256(1000, a_pow_mod)
    )

    # 7 newton-raphson iterations, because 6 iterations will result in non-exact cube roots
    # for values in 10E20 range, and 8 iterations is not that much better than 7.
    # In 7 iterations, we already get good solutions up until ~MAX_UINT256 // 10**18.
    a = unsafe_div(unsafe_add(unsafe_mul(2, a),unsafe_div(_x, a**2)), 3)
    a = unsafe_div(unsafe_add(unsafe_mul(2, a),unsafe_div(_x, a**2)), 3)
    a = unsafe_div(unsafe_add(unsafe_mul(2, a),unsafe_div(_x, a**2)), 3)
    a = unsafe_div(unsafe_add(unsafe_mul(2, a),unsafe_div(_x, a**2)), 3)
    a = unsafe_div(unsafe_add(unsafe_mul(2, a),unsafe_div(_x, a**2)), 3)
    a = unsafe_div(unsafe_add(unsafe_mul(2, a),unsafe_div(_x, a**2)), 3)
    a = unsafe_div(unsafe_add(unsafe_mul(2, a),unsafe_div(_x, a**2)), 3)

    return a


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
def geometric_mean(unsorted_x: uint256[N_COINS], sort: bool = True) -> uint256:
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