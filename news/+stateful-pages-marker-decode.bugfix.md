A `stateful_pages.json` marker that is not valid UTF-8 is now treated as corrupt and rebuilt, instead of raising `UnicodeDecodeError` on every backend start.
