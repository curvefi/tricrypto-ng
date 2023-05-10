from decimal import Decimal

import boa
import pytest


# flake8: noqa: E501
@pytest.fixture(scope="module")
def dydx_optimised_math():

    get_price_impl = """
N_COINS: constant(uint256) = 3
A_MULTIPLIER: constant(uint256) = 10000

@external
@view
def get_p(
    _xp: uint256[N_COINS], _D: uint256, _A_gamma: uint256[N_COINS-1]
) -> (int256, int256, int256, int256[N_COINS-1]):

    D: int256 = convert(_D, int256)
    A: int256 = convert(_A_gamma[0] / 27 / A_MULTIPLIER, int256)
    gamma: int256 = convert(_A_gamma[1], int256)
    x1: int256 = convert(_xp[0], int256)
    x2: int256 = convert(_xp[1], int256)
    x3: int256 = convert(_xp[2], int256)
    gamma2: int256 = unsafe_mul(gamma, gamma)

    S: int256 = x1 + x2 + x3

    # K = P * N**N / D**N.
    # K is dimensionless and has 10**36 precision:
    P: int256 = x1 * x2 * x3
    K: int256 = 27 * P / D * 10**18 / D * 10**18 / D

    # G = 3 * K**2 + N_COINS**N_COINS * A * gamma**2 * (S - D) / D + (gamma + 1) * (gamma + 3) - 2 * K * (2 * gamma + 3)
    # G is in 10**36 space and is also dimensionless.
    G: int256 = (
        3 * K**2 / 10**36
        - 2 * K * (2 * gamma * 10**18 + 3*10**36) / 10**36
        + (gamma2 / D) * (S - D) * A * 27
        + (gamma + 10**18) * (gamma + 3*10**18)
    )

    # G3 = G * D / (N_COINS**N_COINS * A * gamma**2)
    # G3 is also dimensionless and in 10**36 space
    G3: int256 = G * D * 10**18 / (gamma2 * A * 27)

    # p = (x / y) * ((G3 + y) / (G3 + x))
    P_x1x2: int256 = P / x3
    P_x1x3: int256 = P / x2
    p: int256[N_COINS-1] = [
        (x1 * G3 + P_x1x2) / (x2 * G3 + P_x1x2),
        (x1 * G3 + P_x1x3) / (x3 * G3 + P_x1x3),
    ]

    return K, G, G3, p
"""
    return boa.loads(get_price_impl, name="Optimised")


def get_p_decimal(X, D, ANN, gamma):

    X = [Decimal(_) for _ in X]
    P = 10**18 * X[0] * X[1] * X[2]
    N = len(X)
    D = Decimal(D)
    K0 = P / (Decimal(D) / N) ** N

    S = sum(X)

    x = X[0]
    y = X[1]
    z = X[2]

    G = (
        3 * K0**2
        - (2 * K0 * (2 * gamma + 3 * 10**18))
        + (N**N * ANN * gamma**2 * (S - D) / D / 27 / 10000)
        + (gamma + 10**18) * (gamma + 3 * 10**18)
    )
    G3 = 10**18 * 27 * 10000 * G * D / (N**N * ANN * gamma**2) / 10**18
    p = [
        x * (G3 + y) / y * 10**18 / (G3 + x),
        x * (G3 + z) / z * 10**18 / (G3 + x),
    ]
    return K0, G, G3, p


def _check_p(a, b):

    if a != b:
        assert a - b <= 1
        return


def test_against_expt(dydx_optimised_math):

    ANN = 42253659
    gamma = 11720394944313222
    xp = [
        165898964704801767090,
        180089627760498533741,
        479703029155498241214,
    ]
    D = 798348646635793903194
    K0 = 760485295403175182482900094928488925
    G = 203347417738054708080273133352508728
    G3 = 279693542256645859139
    dydx = 950539494815349606
    dzdx = 589388920722357662

    output_vyper = dydx_optimised_math.get_p(xp, D, [ANN, gamma])
    output_python = get_p_decimal(xp, D, ANN, gamma)

    # test python implementation:
    _check_p(output_python[3][0], dydx)
    _check_p(output_python[3][1], dzdx)

    # test vyper implementation
    pass
