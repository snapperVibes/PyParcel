# Although we don't have a command line interface now,
# this file will make setting one up in the future easy.
#
# This is the file passed to Gunicorn.
from flask.cli import FlaskGroup

from pyparcel import app

cli = FlaskGroup(app)

if __name__ == "__main__":
    cli()
