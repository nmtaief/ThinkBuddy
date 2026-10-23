"""Check that all container images in docker-compose.yml are pinned and pullable.

Catches removed, deprecated, or unpinned container images early in CI.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]

COMPOSE_FILE = Path(__file__).resolve().parent.parent / "docker-compose.yml"


def extract_images_from_compose(compose_path: Path) -> list[str]:
    """Parse docker-compose.yml and extract all service image names."""
    if not compose_path.is_file():
        print(f"Error: Compose file not found at {compose_path}", file=sys.stderr)
        sys.exit(1)

    with compose_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    services = data.get("services", {})
    images: list[str] = []

    for _name, srv in services.items():
        image = srv.get("image")
        if image:
            images.append(str(image))

    return images


def validate_image_tag(image: str) -> None:
    """Validate that image has a pinned release tag and does not use :latest."""
    if ":" not in image:
        msg = f"Image '{image}' does not specify a tag. Every image must be pinned."
        raise ValueError(msg)

    # Strip digest if present (e.g., image:tag@sha256:...)
    base_image = image.split("@")[0]
    tag = base_image.split(":")[-1]
    if tag.lower() == "latest":
        msg = f"Image '{image}' uses ':latest'. Every image must be pinned to a specific release."
        raise ValueError(msg)


def check_pull_image(image: str) -> bool:
    """Run docker pull for the given image and verify it succeeds."""
    print(f"==> Pulling image: {image}")
    docker_bin = shutil.which("docker") or "docker"
    result = subprocess.run([docker_bin, "pull", image], check=False)  # noqa: S603
    return result.returncode == 0


def main() -> None:
    images = extract_images_from_compose(COMPOSE_FILE)
    if not images:
        print("No external service images found in compose file.")
        sys.exit(0)

    print(f"Found {len(images)} external images in {COMPOSE_FILE.name}:")
    for img in images:
        print(f"  - {img}")

    # Validate all tags first
    errors: list[str] = []
    for img in images:
        try:
            validate_image_tag(img)
        except ValueError as exc:
            errors.append(str(exc))

    if errors:
        print("\nTag validation errors found:", file=sys.stderr)
        for err in errors:
            print(f"  [ERROR] {err}", file=sys.stderr)
        sys.exit(1)

    # Pull each image
    failed_pulls: list[str] = []
    for img in images:
        if not check_pull_image(img):
            failed_pulls.append(img)

    if failed_pulls:
        print(
            f"\nFailed to pull {len(failed_pulls)} image(s):",
            file=sys.stderr,
        )
        for img in failed_pulls:
            print(f"  [FAILED] {img}", file=sys.stderr)
        sys.exit(1)

    print(f"\nAll {len(images)} images successfully validated and pulled.")
    sys.exit(0)


if __name__ == "__main__":
    main()
