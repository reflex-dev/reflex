"""VMTypes and Regions commands for the Reflex Cloud CLI."""

import json

import click

from reflex_cli import constants
from reflex_cli.utils import console


@click.group()
def vm_types_regions_cli():
    """Commands for VM types and regions."""
    pass


@vm_types_regions_cli.command("create-token")
@click.argument("name", required=True)
@click.option(
    "--duration",
    type=click.IntRange(min=1, max=90),
    default=90,
    help="Duration in days for the token to be valid. Default is 90 days.",
)
@click.option("--token", help="An existing authentication token.")
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
@click.option(
    "--interactive/--no-interactive",
    "-i",
    is_flag=True,
    default=True,
    help="Whether to use interactive mode.",
)
def create_token(
    name: str,
    token: str | None,
    interactive: bool,
    duration: int,
    loglevel: constants.LogLevel = constants.LogLevel.INFO,
):
    """Create a new authentication token for the hosting service."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    authenticated_client = hosting.get_authenticated_client(
        token=token, interactive=interactive
    )

    if duration is None:
        duration = 90  # Default duration is 90 days
        console.info("No duration specified. Using default duration of 90 days.")

    token = hosting.create_token(
        name=name, expiration=duration, client=authenticated_client
    )
    console.success(f"Token: {token}")


@vm_types_regions_cli.command("vmtypes")
@click.option("--token", help="The authentication token.")
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
@click.option(
    "--json/--no-json",
    "-j",
    "as_json",
    is_flag=True,
    help="Whether to output the result in json format.",
)
def get_vm_types(
    token: str | None,
    loglevel: str,
    as_json: bool,
):
    """Retrieve the available VM types."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)

    vmtypes = hosting.get_vm_types()
    if as_json:
        console.print(json.dumps(vmtypes))
        return
    if vmtypes:
        ordered_vmtpes: list[list[str | float]] = [
            [
                value
                for key in ["id", "name", "cpu", "ram"]
                if (value := vmtype.get(key)) is not None
            ]
            for vmtype in vmtypes
        ]
        headers = ["id", "name", "cpu (cores)", "ram (gb)"]
        table = [list(map(str, vmtype)) for vmtype in ordered_vmtpes]
        console.print_table(table, headers=headers)
    else:
        console.print(str(vmtypes))


@vm_types_regions_cli.command(name="regions")
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
@click.option(
    "--json/--no-json",
    "-j",
    "as_json",
    is_flag=True,
    help="Whether to output the result in json format.",
)
def get_deployment_regions(
    loglevel: str,
    as_json: bool,
):
    """List all the regions of the hosting service.
    Areas available for deployment are:
    ams	Amsterdam, Netherlands
    arn	Stockholm, Sweden
    atl	Atlanta, Georgia (US)
    bog	Bogotá, Colombia
    bom	Mumbai, India
    bos	Boston, Massachusetts (US)
    cdg	Paris, France
    den	Denver, Colorado (US)
    dfw	Dallas, Texas (US)
    ewr	Secaucus, NJ (US)
    eze	Ezeiza, Argentina
    fra	Frankfurt, Germany
    gdl	Guadalajara, Mexico
    gig	Rio de Janeiro, Brazil
    gru	Sao Paulo, Brazil
    hkg	Hong Kong, Hong Kong
    iad	Ashburn, Virginia (US)
    jnb	Johannesburg, South Africa
    lax	Los Angeles, California (US)
    lhr	London, United Kingdom
    mad	Madrid, Spain
    mia	Miami, Florida (US)
    nrt	Tokyo, Japan
    ord	Chicago, Illinois (US)
    otp	Bucharest, Romania
    phx	Phoenix, Arizona (US)
    qro	Querétaro, Mexico
    scl	Santiago, Chile
    sea	Seattle, Washington (US)
    sin	Singapore, Singapore
    sjc	San Jose, California (US)
    syd	Sydney, Australia
    waw	Warsaw, Poland
    yul	Montreal, Canada
    yyz	Toronto, Canada.
    """
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)

    list_regions_info = hosting.get_regions()
    if as_json:
        console.print(json.dumps(list_regions_info))
        return
    if list_regions_info:
        headers = list(list_regions_info[0].keys())
        table = [
            [str(value) if value is not None else "" for value in deployment.values()]
            for deployment in list_regions_info
        ]
        console.print_table(table, headers=headers)


@vm_types_regions_cli.command(name="config")
@click.option("--token", help="An existing authentication token.")
@click.option(
    "--interactive/--no-interactive",
    "-i",
    is_flag=True,
    default=True,
    help="Whether to use interactive mode.",
)
def generate_cloud_config(
    token: str | None = None,
    interactive: bool = True,
):
    """Generate a configuration file for the cloud deployment."""
    from reflex_cli.utils import hosting

    hosting.generate_config(interactive=interactive, token=token)
    console.print("Configuration file generated.")
