"""Boot check, run during the image build: import the app and render its OpenAPI, without a database.

An image that cannot import its own code, or cannot describe its routes, fails the build instead of
the first pod.
"""

import sys

from app.main import create_app
from app.settings import Settings


def main() -> int:
    settings = Settings(
        app_env="test",
        database_url="postgresql://app_runtime:unused@127.0.0.1:1/unused",
    )
    app = create_app(settings)
    schema = app.openapi()
    paths = sorted(schema["paths"])
    print(f"boot check ok: {len(paths)} documented paths")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())
