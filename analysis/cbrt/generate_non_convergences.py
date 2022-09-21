import random
from datetime import timedelta

import boa
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
from vyper.utils import SizeLimits

SETTINGS = dict(
    max_examples=1000,
    deadline=timedelta(seconds=1500),
    suppress_health_check=[HealthCheck.filter_too_much],
)
OUTPUT = "./analysis/cbrt/data_non_convergences.csv"


@given(
    val=st.integers(min_value=0, max_value=SizeLimits.MAX_UINT256),
    guess_range=st.floats(min_value=0.01, max_value=10),
)
@settings(**SETTINGS)
def analyse_call(
    cube_root_analysis_contract, analysis_output, val, guess_range
):

    cbrt_ideal = int((val / 10**18) ** (1 / 3) * 10**18)

    # we guess an initial value that is within `guess_range` of ideal
    # output. This range is set as very very wide (1% - 1000% of output):
    initial_value = random.randint(
        int(guess_range * cbrt_ideal), int(guess_range * cbrt_ideal)
    )

    try:

        cube_root_analysis_contract.cbrt(val, initial_value)

        # if the contract does not revert, then we ignore this example
        # and nudge hypothesis to ignore converging examples, since
        # we only care about non-convergences in this script:
        assume(False)

    # if the contract reverts, store data
    except boa.BoaError:

        data = f"{val},{initial_value},{cbrt_ideal}\n"

    # finally: append profiling data:
    analysis_output.append(data)


if __name__ == "__main__":

    # set up cube root range analysis contract:
    # note: this is not the final implementation! it is just a contract
    # that's set up to study cbrt:
    with boa.env.prank(boa.env.generate_address()):
        cube_root_analysis_contract = boa.load(
            "analysis/cbrt/CubeRootAnalysis.vy"
        )

    # initialise vars:
    runs = 100
    global analysis_output
    analysis_output = []

    # run in steps to avoid Flaky Test errors (we're not running tests!):
    for i in range(runs):
        analyse_call(cube_root_analysis_contract, analysis_output)

    # write to output:
    with open(OUTPUT, "w") as f:

        f.write("input,initial_value,cbrt_ideal\n")
        for data in analysis_output:
            f.write(data)
