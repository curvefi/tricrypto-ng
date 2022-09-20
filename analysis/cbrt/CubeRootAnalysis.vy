# @version 0.3.7
# (c) Curve.Fi, 2022
# Study contract for cube root optimisation


MAX_ITER: constant(uint256) = 100
CONVERGENCE_THRESHOLD: constant(uint256) = 10


@external
@view
def cbrt(_x: uint256, x0: uint256 = 0) -> uint256[MAX_ITER]:

    a: uint256 = _x
    a_iter: uint256[MAX_ITER] = empty(uint256[MAX_ITER])
    diff: uint256 = 0

    if x0 != 0:
        a = x0

    x: uint256 = unsafe_mul(_x, 10**18)

    for i in range(MAX_ITER):

        # estimate cube root:
        a_prev: uint256 = a
        a = unsafe_div(
            unsafe_add(
                unsafe_mul(2, a),
                unsafe_div(unsafe_mul(x, 10**18), a**2)
            ), 3
        )
        a_iter[i] = a

        # check for convergence:
        if a > a_prev:
            diff = unsafe_sub(a, a_prev)
        else:
            diff = unsafe_sub(a_prev, a)

        # return if converted:
        if diff <= CONVERGENCE_THRESHOLD:
            return a_iter

    # if we are here, we did not converge and we need to know why:
    return a_iter


@external
@view
def safe_cbrt(_x: uint256, x0: uint256 = 0) -> uint256:

    a: uint256 = _x
    diff: uint256 = 0

    if x0 != 0:
        a = x0

    x: uint256 = _x * 10**18

    for i in range(MAX_ITER):

        # estimate cube root:
        a_prev: uint256 = a
        a = ((2* a) + (x * 10**18) / a**2) / 3

        # check for convergence:
        if a > a_prev:
            diff = a - a_prev
        else:
            diff = a_prev - a

        # return if converted:
        if diff <= CONVERGENCE_THRESHOLD:
            return a

    # if we are here, we did not converge and we need to know why:
    return a
