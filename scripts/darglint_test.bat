@echo off
cd ..

echo "start darglint"

echo "reflex folder"
for /R reflex %%f in (*.py) do (
    echo %%f
    echo %%f|findstr /r "^.*reflex\\rx\.py$"
    if errorlevel 1 (
        uv run darglint %%f
    )
)

echo "tests folder"
for /R tests %%f in (*.py) do (
    echo %%f
    uv run darglint %%f
)

echo "darglint finished"
pause
