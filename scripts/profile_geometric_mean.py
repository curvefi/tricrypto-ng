import os
import random
import typing

import boa
import click
from gmpy2 import mpz, root
from vyper.utils import SizeLimits

MAX_VAL = SizeLimits.MAX_UINT256


def geometric_mean_int(x: typing.List[int]) -> int:
    """for 3 element arrays only"""

    x = [mpz(i) for i in x]
    return int(root(x[0] * x[1] * x[2], 3))


def geometric_mean_cryptomath3_impl():

    source_code = """
N_COINS: constant(uint256) = 3

@internal
@view
def _sort(A0: uint256[N_COINS]) -> uint256[N_COINS]:
    A: uint256[N_COINS] = A0
    for i in range(1, N_COINS):
        x: uint256 = A[i]
        cur: uint256 = i
        for j in range(3):
            y: uint256 = A[cur-1]
            if y > x:
                break
            A[cur] = y
            cur -= 1
            if cur == 0:
                break
        A[cur] = x
    return A


@external
@view
def geometric_mean(unsorted_x: uint256[N_COINS], sort: bool = True) -> uint256:
    x: uint256[N_COINS] = unsorted_x
    if sort:
        x = self._sort(x)
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
"""

    return boa.loads(source_code)


def geometric_mean_cryptomath3optimized_impl():

    source_code = """
N_COINS: constant(uint256) = 3

@internal
@pure
def _sort(unsorted_x: uint256[N_COINS]) -> uint256[N_COINS]:
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


@external
@view
def geometric_mean(_x: uint256[N_COINS], sort: bool = True) -> uint256:

    x: uint256[N_COINS] = _x
    if sort:
        x = self._sort(_x)

    D: uint256 = x[0]
    diff: uint256 = 0
    D_prev: uint256 = 0
    tmp: uint256 = 0

    for i in range(255):

        D_prev = D

        tmp = unsafe_div(unsafe_mul(10**18, x[0]), D)
        tmp = unsafe_div(unsafe_mul(tmp, x[1]), D)
        tmp = unsafe_div(unsafe_mul(tmp, x[2]), D)

        D = unsafe_div(
            unsafe_mul(
                D,
                unsafe_add(unsafe_mul(unsafe_sub(N_COINS, 1), 10**18), tmp)
            ),
            unsafe_mul(N_COINS, 10**18)
        )

        if D > D_prev:
            diff = unsafe_sub(D, D_prev)
        else:
            diff = unsafe_sub(D_prev, D)

        if diff <= 1 or unsafe_mul(diff, 10**18) < D:
            return D

    raise "Did not converge"
"""

    return boa.loads(source_code)


def data_sampler():

    med_range = random.randint(10**16, 10**25)
    spread_range = random.randint(0, 10**4)

    min_range = max(0, med_range - spread_range)

    return [
        random.randint(min_range, med_range + spread_range),
        random.randint(min_range, med_range + spread_range),
        random.randint(min_range, med_range + spread_range),
    ]


def generate_data(num_samples):

    gm_current = geometric_mean_cryptomath3_impl()
    gm_opt = geometric_mean_cryptomath3optimized_impl()

    analysis_output = []
    sampled = []
    while len(analysis_output) < num_samples:

        val = data_sampler()

        if val in sampled:
            continue

        gm_ideal = geometric_mean_int(val)
        gm_old = gm_current.geometric_mean(val)
        gm_old_gasused = gm_current._computation.get_gas_used()

        gm_new = gm_opt.geometric_mean(val)
        gm_new_gasused = gm_opt._computation.get_gas_used()

        data = (
            f"{val[0]},{val[1]},{val[2]},{gm_ideal},{gm_old},{gm_new},"
            f"{gm_old_gasused},{gm_new_gasused}\n"
        )

        analysis_output.append(data)
        sampled.append(val)

    return analysis_output


@click.command()
@click.option("--num_samples", default=10000)
def profile(num_samples):

    filename = "data/geometric_mean_analysis.csv"
    if not os.path.exists("data"):
        os.mkdir("data")

    if not os.path.exists(filename):
        with open(filename, "w") as f:
            f.write(
                "input0,input1,input2,gm_ideal,gm_old,gm_opt,"
                "gm_oldgas,gm_optgas\n"
            )

    generated_data = generate_data(num_samples)

    with open(filename, "a") as f:
        for data in generated_data:
            f.write(data)


if __name__ == "__main__":
    profile()
