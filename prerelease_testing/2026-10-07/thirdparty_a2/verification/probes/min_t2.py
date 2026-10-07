import reflex as rx

calls = []


def make():
    calls.append("called")
    return "x"


class Cfg(rx.State):
    _client = None  # unannotated placeholder


for label, value in (("object()", object()), ("callable", make)):
    try:
        Cfg._client = value
        print(f"{label}: assigned")
    except TypeError as e:
        print(f"{label}: TypeError: {str(e)[:95]}")
print("user callable ran:", calls)
