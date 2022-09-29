import os
import random

import boa
import click
from gmpy2 import iroot, mpz
from vyper.utils import SizeLimits

MAX_VAL = SizeLimits.MAX_UINT256
NON_EXACT_SOLN_EDGE = MAX_VAL // 10**18
CBRT_PRECISION = 10**18


def random_sampler():

    strats = [
        "full_range",
        "binary_exponent",
        "small_numbers",
        "medium_numbers",
        "large_numbers",
    ]

    match random.choice(strats):

        case "full_range":
            return random.randint(0, MAX_VAL)

        case "binary_exponent":
            return 2 ** random.randint(0, 255)

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

        val = random_sampler()

        if val in sampled:
            continue

        cbrt_ideal = int(iroot(mpz(val) * CBRT_PRECISION, 3)[0])

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
