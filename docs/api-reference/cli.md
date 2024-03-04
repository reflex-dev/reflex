# CLI

The `reflex` command line interface (CLI) is a tool for creating and managing Reflex apps.

To see a list of all available commands, run `reflex --help`.

```bash
$ reflex --help

Usage: reflex [OPTIONS] COMMAND [ARGS]...

  Reflex CLI to create, run, and deploy apps.

Options:
  -v, --version  Get the Reflex version.
  --help         Show this message and exit.

Commands:
  db           Subcommands for managing the database schema.
  demo         Run the demo app.
  deploy       Deploy the app to the Reflex hosting service.
  deployments  Subcommands for managing the Deployments.
  export       Export the app to a zip file.
  init         Initialize a new Reflex app in the current directory.
  login        Authenticate with Reflex hosting service.
  logout       Log out of access to Reflex hosting service.
  run          Run the app in the current directory.
```

## Init

The `reflex init` command creates a new Reflex app in the current directory.
If an `rxconfig.py` file already exists already, it will re-initialize the app with the latest template.

```bash
$ reflex init --help
Usage: reflex init [OPTIONS]

  Initialize a new Reflex app in the current directory.

Options:
  --name APP_NAME                 The name of the app to initialize.
  --template [demo|sidebar|blank]
                                  The template to initialize the app with.
  --loglevel [debug|info|warning|error|critical]
                                  The log level to use.  [default:
                                  LogLevel.INFO]
  --help                          Show this message and exit.
```

## Run

The `reflex run` command runs the app in the current directory.

By default it runs your app in development mode.
This means that the app will automatically reload when you make changes to the code.
You can also run in production mode which will create an optimized build of your app.

You can configure the mode, as well as other options through flags.

```bash
$ reflex run --help
Usage: reflex run [OPTIONS]

  Run the app in the current directory.

Options:
  --env [dev|prod]                The environment to run the app in.
                                  [default: Env.DEV]
  --frontend-only                 Execute only frontend.
  --backend-only                  Execute only backend.
  --frontend-port TEXT            Specify a different frontend port.
                                  [default: 3000]
  --backend-port TEXT             Specify a different backend port.  [default:
                                  8000]
  --backend-host TEXT             Specify the backend host.  [default:
                                  0.0.0.0]
  --loglevel [debug|info|warning|error|critical]
                                  The log level to use.  [default:
                                  LogLevel.INFO]
  --help                          Show this message and exit.
```

## Export

You can export your app's frontend and backend to zip files using the `reflex export` command.

The frontend is a compiled NextJS app, which can be deployed to a static hosting service like Github Pages or Vercel.
However this is just a static build, so you will need to deploy the backend separately.
See the self-hosting guide for more information.
