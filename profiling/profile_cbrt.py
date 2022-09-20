import random
from datetime import timedelta

import boa
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from vyper.utils import SizeLimits

PROFILING_SETTINGS = dict(
    max_examples=1000,
    deadline=timedelta(seconds=1500),
)
PROFILING_OUTPUT = "./profiling/data/profile_cbrt.csv"


@given(
    val=st.integers(min_value=0, max_value=SizeLimits.MAX_UINT256 / 10**18),
    guess_range=st.floats(min_value=0.01, max_value=10),
)
@settings(**PROFILING_SETTINGS)
def profile_call(tricrypto_math, profiling_output, val, guess_range):

    cbrt_ideal = int((val / 10**18) ** (1 / 3) * 10**18)

    # we guess an initial value that is within `guess_range` of ideal
    # output. This range is set as very very wide (1% - 1000$ of output):
    initial_value = random.randint(
        int(guess_range * cbrt_ideal), int(guess_range * cbrt_ideal)
    )

    try:

        cbrt_noguess = tricrypto_math.eval(f"self.cbrt({val})")
        gasused_cbrt_noguess = tricrypto_math._computation.get_gas_used()

        cbrt_guess = tricrypto_math.eval(f"self.cbrt({val}, {initial_value})")
        gasused_cbrt_guess = tricrypto_math._computation.get_gas_used()

        profiling_data = (
            f"{val},{initial_value},{cbrt_ideal},{cbrt_noguess},"
            f"{cbrt_guess},{gasused_cbrt_noguess},{gasused_cbrt_guess}\n"
        )

        # if data already exists, assume False example:
        # warning: this will increase the time it takes to profile:
        if profiling_data in profiling_output:
            assume(False)

        # we only want to profile convergences that match output:
        if cbrt_noguess != pytest.approx(
            cbrt_ideal
        ) or cbrt_guess != pytest.approx(cbrt_ideal):
            assume(False)

        profiling_output.append(profiling_data)

    # we don't care about contract errors here, so in case of reversions just
    # assume that the example generated was bad:
    except boa.BoaError:
        assume(False)


if __name__ == "__main__":

    # set up math contract, since we cannot import fixtures:
    with boa.env.prank(boa.env.generate_address()):
        tricrypto_math = boa.load("contracts/CurveCryptoMathOptimized3.vy")

    # initialise vars:
    runs = 10
    global profiling_output
    profiling_output = []

    # profile: run in steps to avoid Flaky Test errors:
    # note: we avoid errors due to flaky tests since that's out of scope:
    for i in range(runs):
        profile_call(tricrypto_math, profiling_output)

    # write to output:
    with open(PROFILING_OUTPUT, "w") as f:
        f.write(
            "input,initial_value,cbrt_ideal,cbrt_implementation_noguess,"
            "cbrt_implementation_guess,gas_used_noguess,"
            "gas_used_initial_value\n"
        )
        for profile in profiling_output:
            f.write(profile)
