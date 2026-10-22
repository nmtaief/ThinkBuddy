"""Script to scaffold core modular monolith packages."""

from pathlib import Path

modules = [
    "auth",
    "families",
    "curriculum",
    "planner",
    "questions",
    "quiz",
    "reviews",
    "chat",
    "progress",
    "revision",
    "notifications",
    "devices",
    "entitlements",
    "admin",
    "audit",
]


def scaffold() -> None:
    base_dir = Path("core")
    for mod in modules:
        mod_dir = base_dir / mod
        mod_dir.mkdir(parents=True, exist_ok=True)

        init_file = mod_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text(f'"""ThinkBuddy core module: {mod}."""\n', encoding="utf-8")

        router_file = mod_dir / "router.py"
        if not router_file.exists():
            content = (
                f'"""API routes for {mod} module."""\n\n'
                "from fastapi import APIRouter\n\n"
                f'router = APIRouter(prefix="/internal/{mod}", tags=["{mod}"])\n'
            )
            router_file.write_text(content, encoding="utf-8")

    print(f"Scaffolded {len(modules)} core modules.")


if __name__ == "__main__":
    scaffold()
