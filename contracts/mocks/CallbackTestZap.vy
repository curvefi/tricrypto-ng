# @version 0.3.8

from vyper.interfaces import ERC20

interface Swap:
    def exchange_extended(
        i: uint256,
        j: uint256,
        dx: uint256,
        min_dy: uint256,
        use_eth: bool,
        sender: address,
        receiver: address,
        cb: bytes32
    ) -> uint256: nonpayable

input_amount: public(uint256)
output_amount: public(uint256)
POOL: immutable(address)


@external
def __init__(_pool: address):
    POOL = _pool


@external
def good_callback(sender: address, receiver: address, coin: address, dx: uint256, dy: uint256):
    assert msg.sender == POOL
    ERC20(coin).transferFrom(sender, POOL, dx)

    # Debug info only, not needed in practice
    self.input_amount = dx
    self.output_amount = dy


@external
def evil_callback(sender: address, receiver: address, coin: address, dx: uint256, dy: uint256):
    assert msg.sender == POOL
    # Transfer the saved imput amount, not dx, to fool the pool
    ERC20(coin).transferFrom(sender, POOL, self.input_amount)

    # Debug info only, not needed in practice
    self.input_amount = dx
    self.output_amount = dy


@external
def set_evil_input_amount(x: uint256):
    self.input_amount = x


@external
def good_exchange(i: uint256, j: uint256, dx: uint256, min_dy: uint256, use_eth: bool = False) -> uint256:
    selector: uint256 = shift(convert(method_id("good_callback(address,address,address,uint256,uint256)"), uint256), 224)
    return Swap(POOL).exchange_extended(
        i, j, dx, min_dy, use_eth, msg.sender, msg.sender,
        convert(selector, bytes32))


@external
def evil_exchange(i: uint256, j: uint256, dx: uint256, min_dy: uint256, use_eth: bool = False) -> uint256:
    selector: uint256 = shift(convert(method_id("evil_callback(address,address,address,uint256,uint256)"), uint256), 224)
    return Swap(POOL).exchange_extended(
        i, j, dx, min_dy, use_eth, msg.sender, msg.sender,
        convert(selector, bytes32))
