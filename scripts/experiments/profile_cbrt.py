import os
import random

import boa
import click
from vyper.utils import SizeLimits

MAX_VAL = SizeLimits.MAX_UINT256


def cbrt_1e18_base(x: int) -> int:
    # x is taken at base 1e36
    # result is at base 1e18

    # avoid division by zero error problem:
    if x == 0:
        return 0

    xx = x * 10**36

    D = x
    for i in range(1000):
        D_prev = D

        # The following implementation has precision errors:
        # D = (2 * D + xx // D * 10**18 // D) // 3
        # this implementation is more precise:
        D = (2 * D + xx // D**2) // 3

        if D > D_prev:
            diff = D - D_prev
        else:
            diff = D_prev - D
        if diff <= 1 or diff * 10**18 < D:
            return D
    raise ValueError("Did not converge")


MAX_CBRT = cbrt_1e18_base(MAX_VAL // 10**36)


def cbrt_1e18_impl():

    source_code = """
@external
@view
def cbrt(x: uint256) -> uint256:
    xx: uint256 = unsafe_mul(x, 10**36)
    if x >= 115792089237316195423570985008687907853269:
        xx = unsafe_mul(x, 10**18)

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

    cbrt_x = unsafe_div(
        unsafe_add(
            unsafe_mul(2, cbrt_x),
            unsafe_div(xx, unsafe_mul(cbrt_x, cbrt_x))
        ),
        3
    )
    cbrt_x = unsafe_div(
        unsafe_add(
            unsafe_mul(2, cbrt_x),
            unsafe_div(xx, unsafe_mul(cbrt_x, cbrt_x))
        ),
        3
    )
    cbrt_x = unsafe_div(
        unsafe_add(
            unsafe_mul(2, cbrt_x),
            unsafe_div(xx, unsafe_mul(cbrt_x, cbrt_x))
        ),
        3
    )
    cbrt_x = unsafe_div(
        unsafe_add(
            unsafe_mul(2, cbrt_x),
            unsafe_div(xx, unsafe_mul(cbrt_x, cbrt_x))
        ),
        3
    )
    cbrt_x = unsafe_div(
        unsafe_add(
            unsafe_mul(2, cbrt_x),
            unsafe_div(xx, unsafe_mul(cbrt_x, cbrt_x))
        ),
        3
    )
    cbrt_x = unsafe_div(
        unsafe_add(
            unsafe_mul(2, cbrt_x),
            unsafe_div(xx, unsafe_mul(cbrt_x, cbrt_x))
        ),
        3
    )
    cbrt_x = unsafe_div(
        unsafe_add(
            unsafe_mul(2, cbrt_x),
            unsafe_div(xx, unsafe_mul(cbrt_x, cbrt_x))
        ),
        3
    )

    if x >= 115792089237316195423570985008687907853269:
        return cbrt_x * 10**6

    return cbrt_x
"""

    return boa.loads(source_code)


def opinionated_data_sampler():

    strats = [
        "full_range",
        "binary_exponent",
        "perfect_cubes",
        "overflow_start",
        "small_numbers",
        "medium_numbers",
        "large_numbers",
        "post_overflow",
    ]

    match random.choice(strats):

        case "full_range":
            return random.randint(0, MAX_VAL)

        case "binary_exponent":
            return 2 ** random.randint(0, 255)

        case "perfect_cubes":
            return random.randint(0, MAX_CBRT) ** 3

        case "overflow_start":
            return random.randint(10**35, 10**40)

        case "small_numbers":
            return random.randint(0, 10**10)

        case "medium_numbers":
            return random.randint(10**10, 10**30)

        case "large_numbers":
            return random.randint(10**30, 10**59)

        case "post_overflow":
            return random.randint(MAX_CBRT, MAX_VAL)


def generate_cbrt_data(
    math_contract: boa.contract.VyperContract,
    num_samples: int = 10000,
):

    analysis_output = []
    sampled = []
    while len(analysis_output) < num_samples:

        val = opinionated_data_sampler()

        if val in sampled:
            continue

        cbrt_ideal = cbrt_1e18_base(val)

        try:

            cbrt_implementation = math_contract.cbrt(val)
            gasused = math_contract._computation.get_gas_used()
            data = f"{val},{cbrt_ideal},{cbrt_implementation},{gasused}\n"

        except boa.BoaError:

            data = f"{val},{cbrt_ideal},-1,-1\n"

        analysis_output.append(data)
        sampled.append(val)

    return analysis_output


@click.command()
@click.option("--num_samples", default=10000)
def profile(num_samples):

    filename = "data/cbrt_analysis.csv"
    if not os.path.exists("data"):
        os.mkdir("data")

    if not os.path.exists(filename):
        with open(filename, "w") as f:
            f.write("input,cbrt_ideal,cbrt_implementation,gasused\n")

    math_contract = cbrt_1e18_impl()
    generated_data = generate_cbrt_data(math_contract, num_samples)

    with open(filename, "a") as f:
        for data in generated_data:
            f.write(data)


if __name__ == "__main__":
    profile()
