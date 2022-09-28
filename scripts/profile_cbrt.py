import boa
from gmpy2 import iroot, mpz
from utils import CBRT_PRECISION, random_sample

PROFILING_OUTPUT = "../data/profile_cbrt.csv"


def profile_call(math_contract, num_samples: int = 1000):

    profile_data = []
    sampled = []
    while len(profile_data) < num_samples:

        val = random_sample()
        if val in sampled:
            continue

        cbrt_ideal = int(iroot(mpz(val) * CBRT_PRECISION, 3)[0])
        try:
            cbrt_implementation = math_contract.eval(f"self.cbrt({val})")
            gasused = math_contract._computation.get_gas_used()
            data = f"{val},{cbrt_ideal},{cbrt_implementation},{gasused}\n"
        except boa.BoaError:
            data = f"{val},{cbrt_ideal},-1,-1\n"

        profile_data.append(data)
        sampled.append(val)

    return profile_data


if __name__ == "__main__":

    import os

    with boa.env.prank(boa.env.generate_address()):
        tricrypto_math = boa.load("contracts/CurveCryptoMathOptimized3.vy")

    # profile: run in steps to avoid Flaky Test errors:
    generated_data = profile_call(tricrypto_math, 10000)

    if not os.path.exists("data"):
        os.mkdir("data")

    if not os.path.exists("data/cbrt_profile"):
        with open("data/cbrt_profile.csv", "w") as f:
            f.write("input,cbrt_ideal,cbrt_implementation,gasused\n")

    with open("data/cbrt_profile.csv", "a") as f:

        for data in generated_data:
            f.write(data)
