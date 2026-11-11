#!/usr/bin/env bash
# CC-2: symlink cases for `reflex export --backend-only` (no frontend build needed), one fresh app dir per case.
# Usage: sym_matrix.sh <new|prev>   -> logs/sym-<case>.<venv>.{out,err,rc} + zip listing in logs/sym-<case>.<venv>.zip.txt
set -u
SB=${SB:-/tmp/claude-0/-home-user/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad/qa}
R=$SB/apps/verify_cc
V=$1
VENV=$SB/envs/cloud_cli-$V
OUT=$R/sym/outside_target          # real dir outside every app dir: file.txt, nested/deep.txt
OVENV=$R/sym/outside_venv          # real uv venv outside every app dir
mkdir -p $R/logs

mkcase() {  # mkcase <name> -> prints the app dir
  local d=$R/sym/$1-$V
  rm -rf $d; mkdir -p $d/cliapp
  cp $R/app-src/rxconfig.py $d/; cp $R/app-src/cliapp/cliapp.py $d/cliapp/; : > $d/cliapp/__init__.py
  echo "plain" > $d/plain.txt
  echo $d
}

runcase() {  # runcase <name> <dir> [extra export args]
  local name=$1 d=$2; shift 2
  (cd $d && env REFLEX_TELEMETRY_ENABLED=false REFLEX_CHECK_LATEST_VERSION=false $VENV/bin/reflex export --backend-only --zip-dest-dir $d "$@" \
      > $R/logs/sym-$name.$V.out 2> $R/logs/sym-$name.$V.err; echo $? > $R/logs/sym-$name.$V.rc)
  if [ -f $d/backend.zip ]; then
    $SB/envs/driver/bin/python -I -c "import zipfile,sys; z=zipfile.ZipFile(sys.argv[1]); print('ENTRIES', len(z.namelist())); [print(n) for n in z.namelist()]; print('TESTZIP', z.testzip())" $d/backend.zip > $R/logs/sym-$name.$V.zip.txt 2>&1
  else
    echo "NO backend.zip" > $R/logs/sym-$name.$V.zip.txt
  fi
  printf '[%s/%s] rc=%s  %s\n' "$name" "$V" "$(cat $R/logs/sym-$name.$V.rc)" "$(grep -E 'ValueError|Error|not in the subpath|Unable' $R/logs/sym-$name.$V.err | tail -1 | cut -c1-160)"
}

# guard
(cd $R && $VENV/bin/python -I -c "import reflex, importlib.metadata as m; assert '/envs/cloud_cli-$V/' in reflex.__file__, reflex.__file__; print('venv ok:', m.version('reflex'))") || exit 99

d=$(mkcase c00-control);                                                                  runcase c00-control $d
d=$(mkcase c01-dirlink-rel-out);   ln -s ../outside_target $d/link_outside;               runcase c01-dirlink-rel-out $d
d=$(mkcase c02-dirlink-abs-out);   ln -s $OUT $d/data;                                    runcase c02-dirlink-abs-out $d
d=$(mkcase c03-nested-dirlink);    mkdir -p $d/assets; ln -s $OUT $d/assets/shared;       runcase c03-nested-dirlink $d
d=$(mkcase c04-dotvenv-real);      (cd $SB && uv --no-config venv --python 3.12 -q $d/.venv); ls -la $d/.venv/bin/python* > $R/logs/sym-c04-dotvenv-real.$V.ls.txt; runcase c04-dotvenv-real $d
d=$(mkcase c05-venv-nodot-real);   (cd $SB && uv --no-config venv --python 3.12 -q $d/venv);  runcase c05-venv-nodot-real $d
d=$(mkcase c06-venvlink-out);      ln -s $OVENV $d/venv;                                  runcase c06-venvlink-out $d
d=$(mkcase c07-filelink-out);      ln -s $OUT/file.txt $d/link.txt;                       runcase c07-filelink-out $d
d=$(mkcase c08-dangling-link);     ln -s /nonexistent/target $d/dangling;                 runcase c08-dangling-link $d
d=$(mkcase c09-link-in-pycache);   mkdir -p $d/__pycache__; ln -s $OUT $d/__pycache__/l;  runcase c09-link-in-pycache $d
d=$(mkcase c10-link-in-dotdir);    mkdir -p $d/.hidden; ln -s $OUT $d/.hidden/l;          runcase c10-link-in-dotdir $d
d=$(mkcase c11-dirlink-excluded);  ln -s $OUT $d/data;                                    runcase c11-dirlink-excluded $d --exclude-from-backend data
d=$(mkcase c12-dirlink-inside);    ln -s cliapp $d/alias;                                 runcase c12-dirlink-inside $d
d=$(mkcase c13-venv-nocfg-link);   mkdir -p $d/env/bin; ln -s /usr/bin/python3 $d/env/bin/python; ln -s $OVENV/lib $d/env/lib; runcase c13-venv-nocfg-link $d
echo SYM-DONE $V
