#!/usr/bin/env bash
# Exercise reflex-release (new = 0.2.1a1 + towncrier 26, prev = 0.2.0 + towncrier 25) on a COPY of the v0.10.1a1 tree.
# Usage: release_matrix.sh <new|prev>
# The copy lives in $ROOT/repo (git init'd, one commit, tag v0.10.1a1). This script tags every package at its
# changelog version (so `detect` sees nothing to publish), adds news fragments in a second commit, then runs
# detect / plan / materialize and saves the resulting changelog diff to logs/release-materialize.<venv>.diff.
# It resets the copy to the base commit when done.
set -u
SB=${SB:-/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa}
ROOT=$SB/apps/cloud_cli
V=$1
RR=$SB/envs/cloud_cli-release-$V/bin/reflex-release
REF=r/pre-2026.10.23-40018338326
G="git -c user.email=qa@example.invalid -c user.name=qa"
cd $ROOT/repo
$G checkout -q -- . && $G clean -fdq
export GITHUB_REF_NAME=$REF GITHUB_OUTPUT=$ROOT/logs/release-gh-output.$V.txt GITHUB_STEP_SUMMARY=$ROOT/logs/release-gh-summary.$V.md
: > $GITHUB_OUTPUT; : > $GITHUB_STEP_SUMMARY
mkdir -p packages/reflex-release/news packages/reflex-hosting-cli/news
BASE=$(git rev-parse HEAD)
# Tag every package at the version its changelog names, so the tree reads as "everything published".
for pkg in $($RR packages); do
  if [ "$pkg" = reflex ]; then cl=CHANGELOG.md; prefix=v; else cl=packages/$pkg/CHANGELOG.md; prefix=$pkg-v; fi
  ver=$(grep -m1 -oE '^## v?[0-9][^ ]*' $cl | sed -E 's/^## v?//')
  [ -n "$ver" ] && git tag -f "$prefix$ver" >/dev/null 2>&1
done
echo "--- detect --ref-name $REF"; $RR detect --ref-name $REF; echo "rc=$?"
# News fragments: orphan (+slug) and PR-numbered, markdown-rich, for two sub-packages.
cat > packages/reflex-hosting-cli/news/+qa-logs-format.feature.md <<'EOF'
`reflex cloud apps logs` prints `timestamp [LEVEL] message` lines. Example:

```bash
reflex cloud apps logs <app-id> --loglevel error
```

- bullet one with `code`
- bullet two with a [link](https://example.invalid)
EOF
cat > packages/reflex-hosting-cli/news/7777.bugfix.md <<'EOF'
Fix *something* with **emphasis** and a second sentence. Unicode: héllo 日本語 🚀.
EOF
cat > packages/reflex-hosting-cli/news/+qa-misc.misc.md <<'EOF'
Internal cleanup.
EOF
cat > packages/reflex-release/news/+qa-towncrier.misc.md <<'EOF'
Rendered with the installed towncrier.
EOF
$G add -A && $G commit -q -m "QA fragments (#4242)"
echo "--- plan --action continued-prerelease --packages reflex-hosting-cli,reflex-release (GITHUB_REF_NAME=$REF)"
$RR plan --action continued-prerelease --packages reflex-hosting-cli,reflex-release > $ROOT/logs/release-plan.$V.out 2> $ROOT/logs/release-plan.$V.err; echo "rc=$?"; cat $ROOT/logs/release-plan.$V.out; head -20 $ROOT/logs/release-plan.$V.err; echo "--- GITHUB_OUTPUT after plan:"; cat $GITHUB_OUTPUT
grep -m1 "^releases=" $GITHUB_OUTPUT | sed "s/^releases=//" > $ROOT/logs/release-plan.$V.json
echo "--- materialize"
$RR materialize --action continued-prerelease --releases "$(cat $ROOT/logs/release-plan.$V.json)" > $ROOT/logs/release-materialize.$V.out 2> $ROOT/logs/release-materialize.$V.err; echo "rc=$?"; head -40 $ROOT/logs/release-materialize.$V.out; head -40 $ROOT/logs/release-materialize.$V.err
git status --short | head -20
git diff --cached > $ROOT/logs/release-materialize.$V.diff; cp packages/reflex-hosting-cli/CHANGELOG.md $ROOT/logs/CHANGELOG-hosting-cli.$V.md; cp packages/reflex-release/CHANGELOG.md $ROOT/logs/CHANGELOG-release.$V.md; cp $GITHUB_STEP_SUMMARY $ROOT/logs/release-summary.$V.md 2>/dev/null
echo "--- untracked after materialize:"; git status --short | grep '^??' | head
echo "--- changelog head (reflex-hosting-cli):"; sed -n 1,40p packages/reflex-hosting-cli/CHANGELOG.md
echo "--- changelog head (reflex-release):"; sed -n 1,12p packages/reflex-release/CHANGELOG.md
echo "--- news dirs after:"; ls packages/reflex-hosting-cli/news packages/reflex-release/news
# Reset the copy for the other version.
$G checkout -q -- . && $G clean -fdq && $G reset -q --hard $BASE
