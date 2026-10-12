from .settings import app_settings


def get_version() -> str:
    try:
        import importlib.metadata

        return importlib.metadata.version("degas-api")
    except importlib.metadata.PackageNotFoundError:
        return "0.0.0-unknown"


__version__: str = get_version()
__all__ = ["app_settings", "__version__"]
