import random

from gmpy2 import iroot, mpz
from vyper.utils import SizeLimits

MAX_VAL = SizeLimits.MAX_UINT256
SQRT_MAX_VAL = int(iroot(mpz(MAX_VAL), 2)[0])
CBRT_PRECISION = 10**18


def random_sample():

    sampling_strat = random.choice(
        ["uniform", "binary_exponent", "concentrated"]
    )

    if sampling_strat == "uniform":
        return random.randint(0, MAX_VAL)

    if sampling_strat == "binary_exponent":
        return 2 ** random.randint(0, 255)

    if sampling_strat == "concentrated":
        return random.randint(0.7 * SQRT_MAX_VAL, 1000 * SQRT_MAX_VAL)
