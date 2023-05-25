import pytest


@pytest.fixture(scope="module")
def cbrt_1e18_base():
    def _impl(x: int) -> int:
        # x is taken at base 1e36
        # result is at base 1e18

        # avoid division by error problem:
        if x == 0:
            return 0

        xx = x * 10**36

        D = x
        for i in range(1000):
            D_prev = D

            # The following implementation has precision errors:
            # D = (2 * D + xx // D * 10**18 // D) // 3
            # this implementation is more precise:
            D = (2 * D + xx // D**2) // 3

            if D > D_prev:
                diff = D - D_prev
            else:
                diff = D_prev - D
            if diff <= 1 or diff * 10**18 < D:
                return D
        raise ValueError("Did not converge")

    return _impl
