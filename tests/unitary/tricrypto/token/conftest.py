import boa
import pytest
from eth_account.messages import encode_structured_data


@pytest.fixture(scope="module")
def skip_unoptimized(optimized):
    if not optimized:
        pytest.skip()
    yield


@pytest.fixture(scope="module")
def sign_permit():
    def _sign_permit(swap, owner, spender, value, deadline, nonce):
        data = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                ],
                "Permit": [
                    {"name": "owner", "type": "address"},
                    {"name": "spender", "type": "address"},
                    {"name": "value", "type": "uint256"},
                    {"name": "nonce", "type": "uint256"},
                    {"name": "deadline", "type": "uint256"},
                ],
            },
            "domain": {
                "name": swap.name(),
                "version": swap.version(),
                "chainId": boa.env.vm.chain_context.chain_id,
                "verifyingContract": swap.address,
            },
            "primaryType": "Permit",
            "message": {
                "owner": owner.address,
                "spender": spender,
                "value": value,
                "nonce": nonce,
                "deadline": deadline,
            },
        }

        permit = encode_structured_data(data)
        return owner.sign_message(permit)

    return _sign_permit
