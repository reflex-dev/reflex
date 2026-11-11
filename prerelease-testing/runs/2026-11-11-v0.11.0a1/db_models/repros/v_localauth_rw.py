# rewrite blog models to Base (from snap_blog_rw) and keep reflex-local-auth pages
import shutil
SB = "/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad"
for f in ["models.py", "blog.py", "db.py"]:
    shutil.copy(f"{SB}/apps/db_models/snap_blog_rw/blog/{f}", f"blog/{f}")
s = open("blog/blog.py").read()
s = s.replace("import reflex as rx\n", "import reflex as rx\nimport reflex_local_auth\n", 1)
s += '''
app.add_page(reflex_local_auth.pages.login_page, route=reflex_local_auth.routes.LOGIN_ROUTE, title="Login")
app.add_page(reflex_local_auth.pages.register_page, route=reflex_local_auth.routes.REGISTER_ROUTE, title="Register")
'''
open("blog/blog.py", "w").write(s)
