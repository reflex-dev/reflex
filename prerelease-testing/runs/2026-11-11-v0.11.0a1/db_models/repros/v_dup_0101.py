import shutil, runpy
SB = "/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad"
for f in ["models.py", "blog.py", "db.py"]:
    shutil.copy(f"{SB}/apps/db_models/snap_blog_rw/blog/{f}", f"blog/{f}")
runpy.run_path(f"{SB}/apps/db_models/repros/v_dup.py")
