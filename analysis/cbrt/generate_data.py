import random
from datetime import timedelta

import boa
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from vyper.utils import SizeLimits

SETTINGS = dict(
    max_examples=1000,
    deadline=timedelta(seconds=1500),
)
OUTPUT = "./analysis/cbrt/data.csv"


@given(
    val=st.integers(min_value=0, max_value=SizeLimits.MAX_UINT256),
    guess_range=st.floats(min_value=0.01, max_value=10),
)
@settings(**SETTINGS)
def analyse_call(
    cube_root_analysis_contract, analysis_output, val, guess_range, max_iter
):

    cbrt_ideal = int((val / 10**18) ** (1 / 3) * 10**18)

    # we guess an initial value that is within `guess_range` of ideal
    # output. This range is set as very very wide (1% - 1000% of output):
    initial_value = random.randint(
        int(guess_range * cbrt_ideal), int(guess_range * cbrt_ideal)
    )

    try:

        cbrt_iter = ",".join(
            [
                str(i)
                for i in cube_root_analysis_contract.cbrt(val, initial_value)
            ]
        )
        cbrt_safe_implementation = cube_root_analysis_contract.safe_cbrt(
            val, initial_value
        )

        data = (
            f"{val},{initial_value},{cbrt_ideal},{cbrt_safe_implementation},"
            f"{cbrt_iter}\n"
        )

        # if data already exists, assume False example since we only care about
        # unique samples, and hypothesis generates lots of redundant samples
        # for including flaky tests:
        if data in analysis_output:
            assume(False)

    # if the contract reverts, we need to note why:
    # TODO: we need way more detailed internal variable surveying
    # for analysing over/under-flowing
    except boa.BoaError:

        revert_data = ",".join(["-1"] * max_iter)

        try:
            cbrt_safe_implementation = cube_root_analysis_contract.safe_cbrt(
                val, initial_value
            )
        except boa.BoaError:
            cbrt_safe_implementation = -1

        data = (
            f"{val},{initial_value},{cbrt_ideal},{cbrt_safe_implementation},"
            f"{revert_data}\n"
        )

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
    max_iter = cube_root_analysis_contract.eval("MAX_ITER")

    # initialise vars:
    runs = 100
    global analysis_output
    analysis_output = []

    # run in steps to avoid Flaky Test errors (we're not running tests!):
    for i in range(runs):
        analyse_call(cube_root_analysis_contract, analysis_output, max_iter)

    # write to output:
    with open(OUTPUT, "w") as f:
        cbrt_iter_headers = ",".join(
            [f"cbrt_iter_{i}" for i in range(max_iter)]
        )
        f.write(
            f"input,initial_value,cbrt_ideal,cbrt_safe_implementation,"
            f"{cbrt_iter_headers}\n"
        )
        for data in analysis_output:
            f.write(data)
