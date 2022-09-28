import random
import typing

from gmpy2 import iroot, mpz
from vyper.utils import SizeLimits

MAX_VAL = SizeLimits.MAX_UINT256
SQRT_MAX_VAL = int(iroot(mpz(MAX_VAL), 2)[0])
CBRT_PRECISION = 10**18


def random_sample(preferential_samples: typing.List = []):

    strats = ["uniform", "binary_exponent"]
    if preferential_samples:
        strats.append("preferential")

    sampling_strat = random.choice(strats)

    if sampling_strat == "uniform":
        return random.randint(0, MAX_VAL)

    if sampling_strat == "binary_exponent":
        return 2 ** random.randint(0, 255)

    if sampling_strat == "preferential":
        sampled_output = MAX_VAL + 1
        while sampled_output > MAX_VAL:
            random_sample = random.choice(preferential_samples)
            sampled_output = int(random_sample * random.uniform(0.5, 1.5))
        return sampled_output
