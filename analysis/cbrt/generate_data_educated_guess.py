import math
from datetime import timedelta

import boa
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from vyper.utils import SizeLimits

SETTINGS = dict(
    max_examples=1000,
    deadline=timedelta(seconds=1500),
)
MAX_VAL = SizeLimits.MAX_UINT256
OUTPUT = "./analysis/cbrt/data_educated_guess.csv"


def log2_guess(n):
    return 2 ** (n / 3) * 1260 ** (n % 3) / 1000 ** (n % 3)


@given(
    val=st.integers(min_value=0, max_value=MAX_VAL),
)
@settings(**SETTINGS)
def generate_cbrt_data(cube_root_analysis_contract, analysis_output, val):

    if val == 0:
        assume(False)

    # ignore edge cases:
    elif val * 10**36 > MAX_VAL:
        assume(False)

    cbrt_ideal = int((val / 10**18) ** (1 / 3) * 10**18)

    # educated guess (given n > 0). based on the following logic:
    # qbrt(a) = qbrt(2**(log2(a))) = 2**(log2(a) / 3) ≈ 2**|log2(a)/3|
    # since we're in 1E18 base, and log2(1E18) = 60 ... :
    initial_value = int(log2_guess(math.log2(val / 10**18)) * 10**18)

    if initial_value**2 > MAX_VAL:
        assume(False)

    # --- GENERATE DATA ---
    cbrt_iter_data = cube_root_analysis_contract.cbrt(val, initial_value)
    cbrt_iter_data_truncated = [i for i in cbrt_iter_data if i != 0]
    cbrt_implementation = cbrt_iter_data_truncated[-1]
    niter = len(cbrt_iter_data_truncated) + 1
    cbrt_iter_str = ",".join([str(i) for i in cbrt_iter_data])

    data = (
        f"{val},{initial_value},{cbrt_ideal},{cbrt_implementation},"
        f"{niter},{cbrt_iter_str}\n"
    )

    # append data if it doesnt already exist:
    if data not in analysis_output:
        analysis_output.append(data)


if __name__ == "__main__":

    # set up cube root range analysis contract:
    # note: this is not the final implementation! it is just a contract
    # that's set up to study cbrt:
    with boa.env.prank(boa.env.generate_address()):
        cube_root_analysis_contract = boa.load(
            "analysis/cbrt/CubeRootAnalysis.vy"
        )
    max_iter = cube_root_analysis_contract.eval("MAX_ITER")

    # initialise vars:
    runs = 100
    global analysis_output
    analysis_output = []

    # run in steps to avoid Flaky Test errors (we're not running tests!):
    for i in range(runs):
        generate_cbrt_data(cube_root_analysis_contract, analysis_output)

    # write to output:
    with open(OUTPUT, "w") as f:
        cbrt_iter_headers = ",".join(
            [f"cbrt_iter_{i}" for i in range(max_iter)]
        )
        f.write(
            f"input,initial_value,cbrt_ideal,cbrt_implementation,niter,"
            f"{cbrt_iter_headers}\n"
        )
        for data in analysis_output:
            f.write(data)
