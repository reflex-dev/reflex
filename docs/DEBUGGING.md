# Debugging

It is possible to run Nextpy apps in dev mode under a debugger.

1. Run Nextpy as a module: `python -m nextpy run --env dev`
2. Set current working directory to the dir containing `xtconfig.py`

## VSCode

The following launch configuration can be used to interactively debug a Nextpy
app with breakpoints.

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Nextpy App",
            "type": "python",
            "request": "launch",
            "module": "nextpy",
            "args": "run --env dev",
            "justMyCode": true,
            "cwd": "${fileDirname}/.."
        }
    ]
}
```