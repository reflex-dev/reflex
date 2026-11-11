# Base models AND the old rx.Model module both imported (same table names, two metadatas)
import shutil
SB = "/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad"
shutil.copy(f"{SB}/apps/db_models/blog_0101_models.py", "blog/models_old.py")
s = open("blog/models_old.py").read()
s = s.replace("    # MIGRATION2\n", "    bio: str | None = None\n").replace("    # MIGRATION2B\n", "    views: int = 0\n")
# make the old model differ: drop the index on post.title and add a column
s = s.replace('title: str = sqlmodel.Field(index=True)', 'title: str = ""\n    legacy_flag: bool = False')
open("blog/models_old.py", "w").write(s)
b = open("blog/blog.py").read()
b = b.replace("from .models import", "from . import models_old  # noqa\nfrom .models import", 1)
open("blog/blog.py", "w").write(b)
