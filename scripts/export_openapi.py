"""Export OpenAPI schemas from FastAPI applications to /docs-generated/openapi.json."""

import json
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.openapi.utils import get_openapi

from gateway.main import app as gateway_app


def export_openapi() -> None:
    output_dir = Path("docs-generated")
    output_dir.mkdir(parents=True, exist_ok=True)

    openapi_schema = get_openapi(
        title=gateway_app.title,
        version=gateway_app.version,
        openapi_version=gateway_app.openapi_version,
        description=gateway_app.description,
        routes=gateway_app.routes,
    )

    output_file = output_dir / "openapi.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2, ensure_ascii=False)

    print(f"Exported Gateway OpenAPI schema to {output_file.resolve()}")


if __name__ == "__main__":
    export_openapi()
