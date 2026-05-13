# pytest-asyncio mode
def pytest_configure(config):
    config.asyncio_mode = "auto"