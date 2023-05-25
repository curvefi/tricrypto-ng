import boa


def test_revert_unauthorised_access(user, tricrypto_factory):

    with boa.env.prank(user):
        with boa.reverts("dev: admin only"):
            tricrypto_factory.set_pool_implementation(
                boa.env.generate_address(), 0
            )

        with boa.reverts("dev: admin only"):
            tricrypto_factory.set_gauge_implementation(
                boa.env.generate_address()
            )

        with boa.reverts("dev: admin only"):
            tricrypto_factory.set_views_implementation(
                boa.env.generate_address()
            )


def test_revert_unauthorised_set_fee_receiver(
    user, tricrypto_factory, fee_receiver
):

    with boa.env.prank(user):
        with boa.reverts("dev: admin only"):
            tricrypto_factory.set_fee_receiver(user)

    assert tricrypto_factory.fee_receiver() == fee_receiver


def test_revert_unauthorised_new_admin(user, tricrypto_factory, owner):

    with boa.env.prank(user), boa.reverts("dev: admin only"):
        tricrypto_factory.commit_transfer_ownership(user)

    with boa.env.prank(owner):
        tricrypto_factory.commit_transfer_ownership(boa.env.generate_address())

    with boa.env.prank(user), boa.reverts("dev: future admin only"):
        tricrypto_factory.accept_transfer_ownership()
