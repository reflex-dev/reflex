"""Copy the hmr_runtime artifacts into the repo (no .web/node_modules/.states/pycache/lockfiles/pids)."""
import shutil, sys
from pathlib import Path
SRC = Path("/tmp/claude-0/-home-user-reflex/80e73324-c7fe-59d8-8ec8-f4f4dc3b5b67/scratchpad/apps/hmr_runtime")
DEST = Path("/home/user/reflex/prerelease-testing/2026-09-10-v0.9.11a1/hmr_runtime")
IGNORE = shutil.ignore_patterns(".web", "node_modules", ".states", "external", "*.db", "__pycache__", "reflex.lock", "*.pid", "assets",
                                "upgrade_index.png", "safari_*.html", "chrome_*.html")  # 10MB full-page shot; browser body dumps duplicate raw_*.html
DEST.mkdir(parents=True, exist_ok=True)
for name in ["hmr_app", "hmr_app_base", "hmr_app_pre7048", "scripts", "logs"]:
    src = SRC / name
    if src.exists():
        shutil.copytree(src, DEST / name, ignore=IGNORE, dirs_exist_ok=True)
shutil.copy2(SRC / "NOTES.md", DEST / "NOTES.md")
files = [p for p in DEST.rglob("*") if p.is_file()]
print(f"copied {len(files)} files, {sum(p.stat().st_size for p in files)/1e6:.1f} MB ->", DEST)
