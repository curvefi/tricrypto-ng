import contextlib

import boa


@contextlib.contextmanager
def mine():
    try:
        yield
    finally:
        boa.env.time_travel(blocks=1)
