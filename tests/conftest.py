def pytest_collection_modifyitems(items):
    for item in items:
        item.add_marker("profile")


pytest_plugins = [
    "tests.fixtures.accounts",
    "tests.fixtures.tokens",
    "tests.fixtures.functions",
    "tests.fixtures.pool",
    "tests.fixtures.factory",
]
