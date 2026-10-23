"""Cross-platform task runner for ThinkBuddy development commands."""

import subprocess
import sys


def run_command(cmd: list[str]) -> int:
    print(f"==> Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=False)  # noqa: S603
    return result.returncode


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python scripts/run.py "
            "[up|down|migrate|test|lint|format|typecheck|export-openapi|check-images]"
        )
        sys.exit(1)

    task = sys.argv[1].lower()

    if task == "up":
        sys.exit(run_command(["docker", "compose", "up", "-d", "--build"]))
    elif task == "down":
        sys.exit(run_command(["docker", "compose", "down"]))
    elif task == "migrate":
        sys.exit(run_command(["alembic", "upgrade", "head"]))
    elif task == "test":
        sys.exit(run_command(["pytest", "-v", "tests/"]))
    elif task == "lint":
        code = run_command(["ruff", "check", "."])
        if code != 0:
            sys.exit(code)
        sys.exit(run_command(["ruff", "format", "--check", "."]))
    elif task == "format":
        run_command(["ruff", "check", "--fix", "."])
        sys.exit(run_command(["ruff", "format", "."]))
    elif task == "typecheck":
        sys.exit(run_command(["mypy", "core", "gateway", "workers"]))
    elif task == "export-openapi":
        sys.exit(run_command(["python", "scripts/export_openapi.py"]))
    elif task == "check-images":
        sys.exit(run_command(["python", "scripts/check_images.py"]))
    else:
        print(f"Unknown task: {task}")
        sys.exit(1)


if __name__ == "__main__":
    main()
