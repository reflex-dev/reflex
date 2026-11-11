"""Module-level client state vars shared by pages."""
import reflex as rx

# named -> global
query = rx.client_state("", name="query")
# named, only rendered on /other (pushed from /backend before it mounts)
late = rx.client_state("late-default", name="late")
# never rendered anywhere, backend only
hidden = rx.client_state("hid-default", name="hidden")
# complex named value
blob = rx.client_state({"n": 0, "items": []}, name="blob")
# unnamed, module-level, used at page level on two pages
page_local = rx.client_state(0)
# two named vars sharing one name with the same default, different modules
dup = rx.client_state("dup-default", name="dup")
