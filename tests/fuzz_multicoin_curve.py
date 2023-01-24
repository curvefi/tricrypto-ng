import unittest
from itertools import permutations

import hypothesis.strategies as st
from hypothesis import given, settings

from tests.utils.simulation_int_many import Curve, solve_D, solve_x

MAX_EXAMPLES_MEAN = 20000
MAX_EXAMPLES_RED = 20000
MAX_EXAMPLES_D = 10000
MAX_EXAMPLES_Y = 5000
MAX_EXAMPLES_YD = 100000
MAX_EXAMPLES_NOLOSS = 100000
MIN_FEE = 5e-5

MIN_XD = 10**16
MAX_XD = 10**20

A_MUL = 3**3 * 10000

MIN_A = int(0.01 * A_MUL)
MAX_A = 1000 * A_MUL

# gamma from 1e-8 up to 0.05
MIN_GAMMA = 10**10
MAX_GAMMA = 5 * 10**16


# Test with 3 coins for simplicity
class TestCurve(unittest.TestCase):
    @given(
        A=st.integers(MIN_A, MAX_A),
        x=st.integers(10**9, 10**15 * 10**18),  # 1e-9 USD to 1e15 USD
        yx=st.integers(
            10**15, 10**18
        ),  # <- ratio 1e18 * y/x, typically 1e18 * 1
        zx=st.integers(
            10**15, 10**18
        ),  # <- ratio 1e18 * z/x, typically 1e18 * 1
        perm=st.integers(0, 5),  # <- permutation mapping to values
        gamma=st.integers(MIN_GAMMA, MAX_GAMMA),
    )
    @settings(max_examples=MAX_EXAMPLES_D)
    def test_D_convergence(self, A, x, yx, zx, perm, gamma):
        # Price not needed for convergence testing
        pmap = list(permutations(range(3)))

        y = x * yx // 10**18
        z = x * zx // 10**18
        curve = Curve(A, gamma, 10**18, 3)
        curve.x = [0] * 3
        i, j, k = pmap[perm]
        curve.x[i] = x
        curve.x[j] = y
        curve.x[k] = z
        assert curve.D() > 0

    @given(
        A=st.integers(MIN_A, MAX_A),
        x=st.integers(10**17, 10**15 * 10**18),  # 0.1 USD to 1e15 USD
        yx=st.integers(5 * 10**14, 20 * 10**20),
        zx=st.integers(5 * 10**14, 20 * 10**20),
        perm=st.integers(0, 5),  # <- permutation mapping to values
        gamma=st.integers(MIN_GAMMA, MAX_GAMMA),
        dx=st.integers(0, 10**18),
        dy=st.integers(0, 10**18),
        dz=st.integers(0, 10**18),
    )
    @settings(max_examples=MAX_EXAMPLES_NOLOSS)
    def test_D_noloss(self, A, x, yx, zx, perm, gamma, dx, dy, dz):
        # Add a little bit and check that D didn't decrease
        pmap = list(permutations(range(3)))

        y = x * yx // 10**18
        z = x * zx // 10**18
        curve = Curve(A, gamma, 10**18, 3)
        curve.x = [0] * 3
        i, j, k = pmap[perm]
        curve.x[i] = x
        curve.x[j] = y
        curve.x[k] = z

        D0 = curve.D()

        curve.x[i] += dx
        curve.x[j] += dy
        curve.x[j] += dz

        D1 = curve.D()

        assert D1 > D0 - D0 // 10**9

    @given(
        A=st.integers(MIN_A, MAX_A),
        x=st.integers(10**17, 10**15 * 10**18),  # $0.1 .. $1e15
        yx=st.integers(10**15, 10**21),
        zx=st.integers(10**15, 10**21),
        gamma=st.integers(MIN_GAMMA, MAX_GAMMA),
        i=st.integers(0, 2),
        j=st.integers(0, 2),
        inx=st.integers(10**15, 10**21),
    )
    @settings(max_examples=MAX_EXAMPLES_Y)
    def test_y_convergence(self, A, x, yx, zx, gamma, i, j, inx):
        if i == j:
            return
        in_amount = x * inx // 10**18
        y = x * yx // 10**18
        z = x * zx // 10**18
        curve = Curve(A, gamma, 10**18, 3)
        curve.x = [x, y, z]
        out_amount = curve.y(in_amount, i, j)
        assert out_amount > 0

    @given(
        A=st.integers(MIN_A, MAX_A),
        x=st.integers(10**17, 10**15 * 10**18),  # 0.1 USD to 1e15 USD
        yx=st.integers(5 * 10**14, 20 * 10**20),
        zx=st.integers(5 * 10**14, 20 * 10**20),
        gamma=st.integers(MIN_GAMMA, MAX_GAMMA),
        i=st.integers(0, 2),
        j=st.integers(0, 2),
        inx=st.integers(3 * 10**15, 3 * 10**20),
    )
    @settings(max_examples=MAX_EXAMPLES_NOLOSS)
    def test_y_noloss(self, A, x, yx, zx, gamma, i, j, inx):
        if i == j:
            return
        y = x * yx // 10**18
        z = x * zx // 10**18
        curve = Curve(A, gamma, 10**18, 3)
        curve.x = [x, y, z]
        in_amount = x * inx // 10**18
        try:
            out_amount = curve.y(in_amount, i, j)
            D1 = curve.D()
        except Exception:
            # Convergence checked separately - we deliberately try unsafe
            # numbers
            return

        is_safe = all(
            f >= MIN_XD and f <= MAX_XD
            for f in [xx * 10**18 // D1 for xx in curve.x]
        )
        curve.x[i] = in_amount
        Dd = curve.D()
        curve.x[j] = out_amount
        try:
            D2 = curve.D()
        except Exception:
            # Convergence checked separately - we deliberately try unsafe
            # numbers
            return
        is_safe &= all(
            f >= MIN_XD and f <= MAX_XD
            for f in [xx * 10**18 // D2 for xx in curve.x]
        )
        if is_safe:
            assert 2 * (D1 - D2) / (D1 + D2) < max(
                MIN_FEE * abs(Dd - D2) / D2, 10 / D2
            )  # Only loss is prevented - gain is ok

    @given(
        A=st.integers(MIN_A, MAX_A),
        D=st.integers(10**17, 10**15 * 10**18),  # 0.1 USD to 1e15 USD
        xD=st.integers(MIN_XD, MAX_XD),
        yD=st.integers(MIN_XD, MAX_XD),
        zD=st.integers(MIN_XD, MAX_XD),
        gamma=st.integers(MIN_GAMMA, MAX_GAMMA),
        j=st.integers(0, 2),
    )
    @settings(max_examples=MAX_EXAMPLES_YD)
    def test_y_from_D(self, A, D, xD, yD, zD, gamma, j):

        xp = [D * xD // 10**18, D * yD // 10**18, D * zD // 10**18]
        y = solve_x(A, gamma, xp, D, j)
        xp[j] = y
        D2 = solve_D(A, gamma, xp)

        is_safe = all(
            f >= MIN_XD and f <= MAX_XD
            for f in [xx * 10**18 // D2 for xx in [xD, yD, zD]]
        )
        if is_safe:
            assert (
                2 * (D - D2) / (D2 + D) < MIN_FEE
            )  # Only loss is prevented - gain is ok


if __name__ == "__main__":
    unittest.main()
