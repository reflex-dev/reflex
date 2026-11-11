# db_models — 0.11.0a1 notes

## Status / resume here
- [x] Step 1: old-style app `blog` built on reflex 0.10.1 (venv `$SB/envs/db_models-up` before upgrade; `$SB/envs/db_models-old` stays 0.10.1),
  `reflex db init` + 2nd revision `add bio views`, data created in Chromium. Snapshot of the 0.10.1 project (incl. reflex.db): `$SB/apps/db_models/snap_blog_0101/`.
- [ ] Step 2: in-place upgrade to 0.11.0a1
- [ ] Step 3: model rewrite to MappedAsDataclass/DeclarativeBase
- [ ] Step 4: serializer e2e
- [ ] Step 5: AdminDash
- [ ] Step 6: deprecated helpers

## Setup
- `SB=/tmp/claude-0/-home-user-reflex/e929f790-b425-5c73-99bc-b00ccb05de29/scratchpad`
- venvs: `cd $SB && uv --no-config venv $SB/envs/db_models-old --python 3.12 && uv --no-config pip install --python $SB/envs/db_models-old/bin/python --only-binary :all: 'reflex[db]==0.10.1' starlette-admin` (same for `db_models-up`).
- Helpers (in `scripts/` here; originals in `$SB/apps/db_models/`): `run.sh <venv> <appdir> <log> dev|prod` (dev 3140/8140, prod single port 3141), `stop.sh <appdir>`, `wait.sh <url>`.
- Drivers: `scripts/pwlib.py`, `scripts/drive_blog.py <base> create|verify <tag>` run with `$SB/envs/driver/bin/python` from `scripts/`.

## Step 1 — old app on 0.10.1
Models (`blog/models.py` in `apps/blog_0101_models.py`): Author (unique index name, nullable email, Enum role, UTC datetime, JSON profile), Post (index title, FK author, datetime),
Tag (unique name), PostTagLink (plain `sqlmodel.SQLModel` link table, composite pk). One-to-many Author.posts, many-to-many Post.tags.
`reflex db init` -> revision 5c38124c7e86; `makemigrations --message "add bio views"` -> 5962b6935088 (`bio` nullable AutoString, `views` Integer server_default 0). 
Chromium (`drive_blog.py create`): 2 authors, duplicate-name IntegrityError surfaced, 3 posts with tags, detail page `/post/[pid]`, bump views: all PASS on 0.10.1, no page errors.
