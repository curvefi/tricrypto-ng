import boa
from gmpy2 import iroot, mpz
from utils import CBRT_PRECISION, random_sample


def generate_cbrt_data(math_contract, num_samples=10000):

    analysis_output = []
    sampled = []
    while len(analysis_output) < num_samples:

        val = random_sample()
        if val in sampled:
            continue

        cbrt_ideal = int(iroot(mpz(val) * CBRT_PRECISION, 3)[0])
        try:
            cbrt_implementation = math_contract.eval(f"self.cbrt({val})")
            data = f"{val},{cbrt_ideal},{cbrt_implementation}\n"
        except boa.BoaError:
            data = f"{val},{cbrt_ideal},-1\n"

        analysis_output.append(data)
        sampled.append(val)

    return analysis_output


if __name__ == "__main__":

    import os

    with boa.env.prank(boa.env.generate_address()):
        math_contract = boa.load("contracts/CurveCryptoMathOptimized3.vy")

    generated_data = generate_cbrt_data(math_contract, 10000)

    if not os.path.exists("data"):
        os.mkdir("data")
    if not os.path.exists("data/cbrt_analysis.csv"):
        with open("data/cbrt_analysis.csv", "w") as f:
            f.write("input,cbrt_ideal,cbrt_implementation\n")

    with open("data/cbrt_analysis.csv", "a") as f:

        for data in generated_data:
            f.write(data)
