import click
from dotenv import load_dotenv
from .tools import loadConfig


load_dotenv()


@click.command()
@click.option(
    "-c",
    "--config",
    envvar="HAKKAN_CONFIG",
    default="./hakkan.toml",
    help="Hakkan configuration file",
)
@click.option(
    "-v",
    "--verbose",
    default=False,
    envvar="HAKKAN_VERBOSE",
)
def cli(config, verbose):
    """Publish a project

    Load and process the given project's .toml configuration file then exit.

    The default project filename is `hakkan.toml` and can be given by setting the HAKKAN_CONFIG environment variable.
    \f

    :param config
    """
    click.echo(f"config: {config}, verbose: {verbose}")
    loadConfig(config)


if __name__ == "__main__":
    cli()
