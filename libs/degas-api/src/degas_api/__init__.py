from importlib.metadata import PackageNotFoundError, version

from .settings import app_settings


def get_version() -> str:
    try:
        return version("degas-api")
    except PackageNotFoundError:
        return "0.0.0"


__version__: str = get_version()
__all__ = ["app_settings", "__version__"]
