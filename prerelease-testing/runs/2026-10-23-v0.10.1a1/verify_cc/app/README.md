Test app used for the deploy archive comparison: `reflex init --template blank --name cliapp`, then rxconfig.py and
cliapp/cliapp.py replaced by the files here, plus this fixture tree created with shell commands (see NOTES.md,
"Deploy archive"): assets/logo.png (1x1 PNG), assets/big.txt (400 kB base64 random), assets/sub/repetitive.txt (+ a
user-supplied .gz of it), big_excluded/{marker.txt,nested/blob.bin}, fakevenv/pyvenv.cfg, notvenv/keep.py,
.hidden_dir/secret.txt, reflex.db, .env.local, symlink link_to_excluded -> big_excluded, hard link
hardlink_alias.py == hardlink_source.py.
