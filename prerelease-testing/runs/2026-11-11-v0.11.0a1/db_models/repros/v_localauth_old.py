# old rx.Model app + reflex-local-auth pages
s = open("blog/blog.py").read()
s = s.replace("import reflex as rx\n", "import reflex as rx\nimport reflex_local_auth\n", 1)
s += '''
app.add_page(reflex_local_auth.pages.login_page, route=reflex_local_auth.routes.LOGIN_ROUTE, title="Login")
app.add_page(reflex_local_auth.pages.register_page, route=reflex_local_auth.routes.REGISTER_ROUTE, title="Register")
'''
open("blog/blog.py", "w").write(s)
