"""Copy the tested assistant code into the web app's server functions, so the site runs the exact code the tests check."""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ("assistant.py", "notes.py", "copilot.py")
DEST = ROOT / "web" / "api" / "_bearing"


def sync():
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "__init__.py").write_text("", encoding="utf-8")
    for f in FILES:
        shutil.copyfile(ROOT / "bearing" / f, DEST / f)


if __name__ == "__main__":
    sync()
    print("synced", ", ".join(FILES))
