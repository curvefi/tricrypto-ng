# @version 0.3.7
# (c) Curve.Fi, 2023

"""
@title CurveCryptoViews3Optimized
@license MIT
@author Curve.Fi
@notice This contract contains view-only external methods which can be
        gas-inefficient when called from smart contracts.
"""

from vyper.interfaces import ERC20


interface Curve:
    def A() -> uint256: view
    def gamma() -> uint256: view
    def price_scale(i: uint256) -> uint256: view
    def price_oracle(i: uint256) -> uint256: view
    def get_virtual_price() -> uint256: view
    def balances(i: uint256) -> uint256: view
    def D() -> uint256: view
    def fee_calc(xp: uint256[N_COINS]) -> uint256: view
    def calc_token_fee(
        amounts: uint256[N_COINS], xp: uint256[N_COINS]
    ) -> uint256: view
    def future_A_gamma_time() -> uint256: view
    def totalSupply() -> uint256: view
    def precisions() -> uint256[N_COINS]: view


interface Math:
    def newton_D(
        ANN: uint256,
        gamma: uint256,
        x_unsorted: uint256[N_COINS],
        K0_prev: uint256
    ) -> uint256: view
    def get_y(
        ANN: uint256,
        gamma: uint256,
        x: uint256[N_COINS],
        D: uint256,
        i: uint256,
    ) -> uint256[2]: view
    def cbrt(x: uint256) -> uint256: view


N_COINS: constant(uint256) = 3
PRECISION: constant(uint256) = 10**18

math: public(immutable(address))


@external
def __init__(_math: address):
    math = _math


@external
@view
def get_dy(
    i: uint256, j: uint256, dx: uint256, swap: address
) -> uint256:

    dy: uint256 = 0
    xp: uint256[N_COINS] = empty(uint256[N_COINS])
    dy, xp = self._get_dy_nofee(i, j, dx, swap)

    dy -= Curve(swap).fee_calc(xp) * dy / 10**10

    return dy


@view
@external
def get_dx(
    i: uint256, j: uint256, dy: uint256, swap: address
) -> uint256:

    dx: uint256 = 0
    xp: uint256[N_COINS] = empty(uint256[N_COINS])
    dx, xp = self._get_dx_fee(i, j, dy, swap)

    # TODO: dx calculated assumes dy has fee subtracted already. What do?

    return 0


@view
@external
def calc_token_amount(
    amounts: uint256[N_COINS], deposit: bool, swap: address
) -> uint256:

    d_token: uint256 = 0
    amountsp: uint256[N_COINS] = empty(uint256[N_COINS])
    xp: uint256[N_COINS] = empty(uint256[N_COINS])

    d_token, amountsp, xp = self._calc_dtoken_nofee(amounts, deposit, swap)
    d_token -= (
        Curve(swap).calc_token_fee(amountsp, xp) * d_token / 10**10 + 1
    )

    return d_token


@external
@view
def calc_fee_get_dy(i: uint256, j: uint256, dx: uint256, swap: address
) -> uint256:

    dy: uint256 = 0
    xp: uint256[N_COINS] = empty(uint256[N_COINS])
    dy, xp = self._get_dy_nofee(i, j, dx, swap)

    return Curve(swap).fee_calc(xp) * dy / 10**10


@view
@external
def calc_fee_token_amount(
    amounts: uint256[N_COINS], deposit: bool, swap: address
) -> uint256:

    d_token: uint256 = 0
    amountsp: uint256[N_COINS] = empty(uint256[N_COINS])
    xp: uint256[N_COINS] = empty(uint256[N_COINS])
    d_token, amountsp, xp = self._calc_dtoken_nofee(amounts, deposit, swap)

    return Curve(swap).calc_token_fee(amountsp, xp) * d_token / 10**10 + 1


@internal
@view
def _calc_D_ramp(
    A: uint256,
    gamma: uint256,
    xp: uint256[N_COINS],
    precisions: uint256[N_COINS],
    price_scale: uint256[N_COINS - 1],
    swap: address
) -> uint256:

    D: uint256 = Curve(swap).D()
    if Curve(swap).future_A_gamma_time() > 0:
        _xp: uint256[N_COINS] = xp
        _xp[0] *= precisions[0]
        for k in range(N_COINS - 1):
            _xp[k + 1] = (
                _xp[k + 1] * price_scale[k] * precisions[k + 1] / PRECISION
            )
        D = Math(math).newton_D(A, gamma, _xp, 0)

    return D


@internal
@view
def _get_dx_fee(
    i: uint256, j: uint256, dy: uint256, swap: address
) -> (uint256, uint256[N_COINS]):

    # here, dy must include fees (and 1 wei offset)

    assert i != j and i < N_COINS and j < N_COINS, "coin index out of range"
    assert dy > 0, "do not exchange out 0 coins"

    xp: uint256[N_COINS] = empty(uint256[N_COINS])
    precisions: uint256[N_COINS] = empty(uint256[N_COINS])
    price_scale: uint256[N_COINS-1] = empty(uint256[N_COINS-1])
    D: uint256 = 0
    token_supply: uint256 = 0
    A: uint256 = 0
    gamma: uint256 = 0

    xp, D, token_supply, price_scale, A, gamma, precisions = self._prep_calc(swap)

    # adjust xp with output dy
    xp[j] -= dy
    xp[0] *= precisions[0]
    for k in range(N_COINS - 1):
        xp[k + 1] = xp[k + 1] * price_scale[k] * precisions[k + 1] / PRECISION

    x_out: uint256[2] = Math(math).get_y(A, gamma, xp, D, i)
    dx: uint256 = x_out[0] - xp[i]
    xp[i] = x_out[0]
    if i > 0:
        dx = dx * PRECISION / price_scale[i - 1]
    dx /= precisions[i]

    return dx, xp


@internal
@view
def _get_dy_nofee(
    i: uint256, j: uint256, dx: uint256, swap: address
) -> (uint256, uint256[N_COINS]):

    assert i != j and i < N_COINS and j < N_COINS, "coin index out of range"
    assert dx > 0, "do not exchange 0 coins"

    xp: uint256[N_COINS] = empty(uint256[N_COINS])
    precisions: uint256[N_COINS] = empty(uint256[N_COINS])
    price_scale: uint256[N_COINS-1] = empty(uint256[N_COINS-1])
    D: uint256 = 0
    token_supply: uint256 = 0
    A: uint256 = 0
    gamma: uint256 = 0

    xp, D, token_supply, price_scale, A, gamma, precisions = self._prep_calc(swap)

    # adjust xp with input dx
    xp[i] += dx
    xp[0] *= precisions[0]
    for k in range(N_COINS - 1):
        xp[k + 1] = xp[k + 1] * price_scale[k] * precisions[k + 1] / PRECISION

    y_out: uint256[2] = Math(math).get_y(A, gamma, xp, D, j)
    dy: uint256 = xp[j] - y_out[0] - 1
    xp[j] = y_out[0]
    if j > 0:
        dy = dy * PRECISION / price_scale[j - 1]
    dy /= precisions[j]

    return dy, xp


@internal
@view
def _calc_dtoken_nofee(
    amounts: uint256[N_COINS], deposit: bool, swap: address
) -> (uint256, uint256[N_COINS], uint256[N_COINS]):

    xp: uint256[N_COINS] = empty(uint256[N_COINS])
    precisions: uint256[N_COINS] = empty(uint256[N_COINS])
    price_scale: uint256[N_COINS-1] = empty(uint256[N_COINS-1])
    D0: uint256 = 0
    token_supply: uint256 = 0
    A: uint256 = 0
    gamma: uint256 = 0

    xp, D0, token_supply, price_scale, A, gamma, precisions = self._prep_calc(swap)

    amountsp: uint256[N_COINS] = amounts
    if deposit:
        for k in range(N_COINS):
            xp[k] += amounts[k]
    else:
        for k in range(N_COINS):
            xp[k] -= amounts[k]

    xp[0] *= precisions[0]
    amountsp[0] *= precisions[0]
    for k in range(N_COINS - 1):
        p: uint256 = price_scale[k] * precisions[k + 1]
        xp[k + 1] = xp[k + 1] * p / PRECISION
        amountsp[k + 1] = amountsp[k + 1] * p / PRECISION

    D: uint256 = Math(math).newton_D(A, gamma, xp, 0)
    d_token: uint256 = token_supply * D / D0

    if deposit:
        d_token -= token_supply
    else:
        d_token = token_supply - d_token

    return d_token, amountsp, xp


@internal
@view
def _prep_calc(swap: address) -> (
    uint256[N_COINS],
    uint256,
    uint256,
    uint256[N_COINS-1],
    uint256,
    uint256,
    uint256[N_COINS]
):

    precisions: uint256[N_COINS] = Curve(swap).precisions()
    token_supply: uint256 = Curve(swap).totalSupply()
    xp: uint256[N_COINS] = empty(uint256[N_COINS])
    for k in range(N_COINS):
        xp[k] = Curve(swap).balances(k)

    price_scale: uint256[N_COINS - 1] = empty(uint256[N_COINS - 1])
    for k in range(N_COINS - 1):
        price_scale[k] = Curve(swap).price_scale(k)

    A: uint256 = Curve(swap).A()
    gamma: uint256 = Curve(swap).gamma()
    D: uint256 = self._calc_D_ramp(
        A, gamma, xp, precisions, price_scale, swap
    )

    return xp, D, token_supply, price_scale, A, gamma, precisions
