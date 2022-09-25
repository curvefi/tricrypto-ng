import math
import random
from datetime import timedelta

import boa
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from vyper.utils import SizeLimits

PROFILING_SETTINGS = dict(
    max_examples=1000,
    deadline=timedelta(seconds=1500),
)
PROFILING_OUTPUT = "./profiling/data/profile_cbrt.csv"
MAX_VAL = SizeLimits.MAX_UINT256


def log2_guess(n):
    return 2 ** (n / 3) * 1260 ** (n % 3) / 1000 ** (n % 3)


@given(
    val=st.integers(min_value=0, max_value=MAX_VAL),
    guess_range=st.floats(min_value=0.01, max_value=10),
)
@settings(**PROFILING_SETTINGS)
def profile_call(tricrypto_math, profiling_output, val, guess_range):

    if val == 0:
        assume(False)

    # ignore edge cases:
    elif val * 10**36 > MAX_VAL:
        assume(False)

    cbrt_ideal = int((val / 10**18) ** (1 / 3) * 10**18)

    # we guess an initial value that is within `guess_range` of ideal
    # output. This range is set as very very wide (1% - 1000$ of output):
    initial_value = random.randint(
        int(guess_range * cbrt_ideal), int(guess_range * cbrt_ideal)
    )

    # educated guess (given n > 0). based on the following logic:
    # qbrt(a) = qbrt(2**(log2(a))) = 2**(log2(a) / 3) ≈ 2**|log2(a)/3|
    # since we're in 1E18 base, and log2(1E18) = 60 ... :
    educated_guess = int(log2_guess(math.log2(val / 10**18)) * 10**18)

    # initial value's square cannot be larger than MAX_UINT256:
    if initial_value**2 > MAX_VAL or educated_guess**2 > MAX_VAL:
        assume(False)

    else:

        # ---- GENERATE DATA ----

        # no initial guesses:
        cbrt_noguess = tricrypto_math.eval(f"self.cbrt({val})")
        gasused_cbrt_noguess = tricrypto_math._computation.get_gas_used()

        # randomised initial guess:
        cbrt_guess = tricrypto_math.eval(f"self.cbrt({val}, {initial_value})")
        gasused_cbrt_guess = tricrypto_math._computation.get_gas_used()

        # educated guess:
        cbrt_educated_guess = tricrypto_math.eval(
            f"self.cbrt({val}, {educated_guess})"
        )
        gasused_cbrt_educated_guess = (
            tricrypto_math._computation.get_gas_used()
        )

        profiling_data = (
            f"{val},{initial_value},{educated_guess},{cbrt_ideal},"
            f"{cbrt_noguess},{cbrt_guess},{cbrt_educated_guess},"
            f"{gasused_cbrt_noguess},{gasused_cbrt_guess},"
            f"{gasused_cbrt_educated_guess}\n"
        )

        # only save data that isn't already stored:
        if profiling_data not in profiling_output:
            profiling_output.append(profiling_data)


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
            "input,initial_value,educated_guess,cbrt_ideal,"
            "cbrt_implementation_noguess,cbrt_implementation_guess,"
            "cbrt_implementation_educated_guess,gas_used_noguess,"
            "gas_used_initial_value,gas_used_educated_guess\n"
        )
        for profile in profiling_output:
            f.write(profile)
