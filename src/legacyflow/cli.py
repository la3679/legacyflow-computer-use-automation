import typer

app = typer.Typer(help="Discover, save, and deterministically replay UI capabilities.")


@app.command()
def version() -> None:
    """Print the application version."""
    typer.echo("LegacyFlow 0.1.0")


if __name__ == "__main__":
    app()
