from degas_api import __version__


FASTAPI_TITLE = "DeGAS API"
FASTAPI_SUMMARY = ""
FASTAPI_DESCRIPTION = """
"""


def startup_message(host: str, port: int, docs_url: str) -> str:
    return f"""

DeGAS API
Version {__version__}

Open the Docs via Swagger UI: http://{host}:{port}{docs_url}

"""
