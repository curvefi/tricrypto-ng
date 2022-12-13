import boa
import pytest
from eth_account._utils.structured_data.hashing import (
    hash_domain,
    hash_message,
)
from eth_account.messages import SignableMessage


@pytest.fixture(scope="module")
def skip_unoptimized(optimized):
    if not optimized:
        pytest.skip()
    yield


@pytest.fixture(scope="module")
def sign_permit():
    def _sign_permit(swap, owner, spender, value, deadline, nonce, salt):
        data = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                    {"name": "salt", "type": "bytes32"},
                ],
                "Permit": [
                    {"name": "owner", "type": "address"},
                    {"name": "spender", "type": "address"},
                    {"name": "value", "type": "uint256"},
                    {"name": "nonce", "type": "uint256"},
                    {"name": "deadline", "type": "uint256"},
                ],
            },
            "primaryType": "Permit",
            "domain": {
                "name": swap.name(),
                "version": swap.version(),
                "chainId": boa.env.vm.chain_context.chain_id,
                "verifyingContract": swap.address,
                "salt": salt,
            },
            "message": {
                "owner": owner.address,
                "spender": spender,
                "value": value,
                "nonce": nonce,
                "deadline": deadline,
            },
        }

        signable_message = SignableMessage(
            b"\x01", hash_domain(data), hash_message(data)
        )
        return owner.sign_message(signable_message)

    return _sign_permit
