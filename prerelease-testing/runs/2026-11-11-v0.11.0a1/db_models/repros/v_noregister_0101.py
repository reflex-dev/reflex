import shutil
SB = "/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad"
for f in ["models.py", "blog.py", "db.py"]:
    shutil.copy(f"{SB}/apps/db_models/snap_blog_rw/blog/{f}", f"blog/{f}")
p='blog/models.py'; s=open(p).read(); s=s.replace("rx.ModelRegistry.register(Base)\n","",1); open(p,'w').write(s)
