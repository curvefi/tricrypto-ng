import random

import boa

A_MULTIPLIER = 10000


def geometric_mean(x):
    N = len(x)
    x = sorted(x, reverse=True)
    D = x[0]
    for i in range(255):
        D_prev = D
        tmp = 10**18
        for _x in x:
            tmp = tmp * _x // D
        D = D * ((N - 1) * 10**18 + tmp) // (N * 10**18)
        diff = abs(D - D_prev)
        if diff <= 1 or diff * 10**18 < D:
            return D

    raise ValueError("Did not converge")


print()
print("--------------- INPUTS ------------------------")

multiplier = 10**9

x = int(random.uniform(0.6, 1.5) * 1e18 * multiplier)
y = int(random.uniform(0.6, 1.5) * 1e18 * multiplier)
z = int(random.uniform(0.6, 1.5) * 1e18 * multiplier)

x_unsorted = [x, y, z]

_A = 6
ANN = int(_A * 27 * A_MULTIPLIER)
g = 0.002
gamma = int(0.002 * 10**18)

print("xp:", x_unsorted)
print("ANN:", ANN)
print("gamma:", gamma)
print()

print("--------------- NEWTON'S METHOD ------------------------")


def newton_D(A, gamma, x_unsorted):

    x = sorted(x_unsorted, reverse=True)

    D = len(x) * geometric_mean(x)
    S = sum(x)
    N = len(x)

    for i in range(255):

        D_prev = D

        print(f"D in step {i}:", D)

        K0 = 10**18
        for _x in x:
            K0 = K0 * _x * N // D

        _g1k0 = abs(gamma + 10**18 - K0)

        # D / (A * N**N) * _g1k0**2 / gamma**2
        mul1 = (
            10**18 * D // gamma * _g1k0 // gamma * _g1k0 * A_MULTIPLIER // A
        )

        # 2*N*K0 / _g1k0
        mul2 = (2 * 10**18) * N * K0 // _g1k0

        neg_fprime = (
            (S + S * mul2 // 10**18) + mul1 * N // K0 - mul2 * D // 10**18
        )
        assert neg_fprime > 0  # Python only: -f' > 0

        # D -= f / fprime
        D = (D * neg_fprime + D * S - D**2) // neg_fprime - D * (
            mul1 // neg_fprime
        ) // 10**18 * (10**18 - K0) // K0

        if D < 0:
            D = -D // 2
        if abs(D - D_prev) <= max(100, D // 10**14):
            print("Newton's method converged to:", D)
            return D

    raise ValueError("Newton's method did not converge")


D_newton = newton_D(ANN, gamma, x_unsorted)

print()
print("--------------- SECANT METHOD ------------------------")
print()


def _C(A, gamma, S, P, D):

    gamma2 = gamma**2 // 10**18

    # d0 = -1.0 / 27 * D**3 * (1.0 + g)**2 # D^9
    d0 = (
        -D
        * D
        // 10**18
        * D
        // 10**18
        * (10**18 + gamma) ** 2
        // 10**36
        // 27
    )

    # d1 = (3 * P + 4 * g * P + P * g**2 - 27 * A * g**2 * P) # D^6
    d1 = (3 * 10**18 + 4 * gamma + (1 - 27 * A) * gamma2) * P // 10**18

    # d2 = 27 * A * g**2 * (P / D) * S # D^5
    d2 = 27 * A * gamma2 * P // 10**18 * S // D

    # d3 = (-81 - 54 * g) * (P / D)**2  / D # D^3
    d3 = (-81 * 10**18 - 54 * gamma) * P // D * P // D * 10**18 // D

    # d4 = 729 * (P / D / D)**3 # D^0
    d4 = P * 10**18 // D * 10**18 // D
    d4 = 729 * (d4 * d4 // 10**18 * d4 // 10**18)

    return d0 + d1 + d2 + d3 + d4


def secant_D(ANN, gamma, x_unsorted):

    x = sorted(x_unsorted, reverse=True)

    A = ANN // 27 // A_MULTIPLIER

    S = x[0] + x[1] + x[2]
    P = x[0] * x[1] // 10**18 * x[2] // 10**18

    D_prev_2 = S * 10**18 // (11 * 10**17)
    D = S

    C_D_prev_2 = _C(A, gamma, S, P, D_prev_2)

    for i in range(255):

        D_prev = D
        C_D_prev = _C(A, gamma, S, P, D_prev)
        inv = C_D_prev - C_D_prev_2

        D = D_prev - C_D_prev * (D_prev - D_prev_2) // inv

        print(f"D_secant in step {i}: {D}")

        if abs(D - D_prev) < max(100, D // 10**10):
            return D

        C_D_prev_2 = C_D_prev
        D_prev_2 = D_prev

    raise "Secant method did not converge"


D_secant = secant_D(ANN, gamma, x_unsorted)

print()
print("----------------------------------------------------------")
print()
print(
    "Python Implementation: abs(D_newton - D_secant) / abs(D_newton)",
    abs(D_newton - D_secant) / abs(D_newton),
)
print()
print("D secant method     :", D_secant)
print("D Newton's method   :", D_newton)

print()
print("-------------------- CONTRACTS ---------------------------")
print()

math = boa.load("contracts/CurveCryptoMathOptimized3.vy")

D_newton_contract = math.newton_D(ANN, gamma, x_unsorted)
D_newton_gas = math._computation.get_gas_used()
D_secant_contract = math.secant_D(ANN, gamma, x_unsorted)
D_secant_gas = math._computation.get_gas_used()

print(f"D_newton_contract (cost: {D_newton_gas} gas):", D_newton_contract)
print(f"D_secant_contract (cost: {D_secant_gas} gas):", D_secant_contract)

print(
    "Vyper Implementation: abs(D_newton - D_secant) / abs(D_newton)",
    abs(D_newton_contract - D_secant_contract) / abs(D_newton_contract),
)
print()
