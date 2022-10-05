import os
import random

import boa
import click
from vyper.utils import SizeLimits

MAX_VAL = SizeLimits.MAX_UINT256


def cbrt_1e18_base(x: int) -> int:
    # x is taken at base 1e36
    # result is at base 1e18

    # avoid division by error problem:
    if x == 0:
        return 0

    # xx = x * 10**18
    xx = x * 10**36

    D = x
    diff = 0
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


def opinionated_data_sampler():

    strats = [
        "full_range",
        "binary_exponent",
        "perfect_cubes",
        "overflow_start",
        "small_numbers",
        "medium_numbers",
        "large_numbers",
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

            cbrt_implementation = math_contract.eval(f"self.cbrt({val})")
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

    with boa.env.prank(boa.env.generate_address()):
        math_contract = boa.load("contracts/CurveCryptoMathOptimized3.vy")

    generated_data = generate_cbrt_data(math_contract, num_samples)

    with open(filename, "a") as f:

        for data in generated_data:
            f.write(data)


if __name__ == "__main__":
    profile()
