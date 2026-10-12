import logging


def get_version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("pydegas")
    except PackageNotFoundError:
        return "0.0.0"


__version__: str = get_version()


logging.getLogger(__name__).addHandler(logging.NullHandler())
