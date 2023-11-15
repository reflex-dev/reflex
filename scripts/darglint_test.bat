@echo off
cd ..

echo "start darglint"

echo "nextpy folder"
for /R nextpy %%f in (*.py) do (
    echo %%f
    echo %%f|findstr /r "^.*nextpy\\xt\.py$"
    if errorlevel 1 (
        poetry run darglint %%f
    )
)

echo "tests folder"
for /R tests %%f in (*.py) do (
    echo %%f
    poetry run darglint %%f
)

echo "darglint finished"
pause
