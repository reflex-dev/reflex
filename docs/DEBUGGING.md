# Debugging

It is possible to run Reflex apps in dev mode under a debugger.

1. Run Reflex as a module: `python -m reflex run --env dev`
2. Set current working directory to the dir containing `rxconfig.py`

## VSCode

The following launch configuration can be used to interactively debug a Reflex
app with breakpoints.

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Reflex App",
            "type": "python",
            "request": "launch",
            "module": "reflex",
            "args": "run --env dev",
            "justMyCode": true,
            "cwd": "${fileDirname}/.."
        }
    ]
}
```