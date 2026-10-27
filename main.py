"""Start the platform using the same setup as the IDE Run button."""
import subprocess
from pathlib import Path


def main():
    project_root = Path(__file__).resolve().parent
    return subprocess.call(["bash", str(project_root / ".derle" / "run.sh")], cwd=project_root)


if __name__ == "__main__":
    raise SystemExit(main())
