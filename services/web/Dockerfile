# We could have a small image size by using a multi-stage build,
# but the additional complexity isn't worth it as Docker is new to the team (as of late 2020)
FROM python:3.8.6-slim

# Not running as root is a standard saftey procedure
# The username "thalia" was choosen as a spiritual successor to the postgres bot "sylvia"
RUN useradd --create-home --shell /bin/bash thalia

WORKDIR usr/src/app

# Unbuffered: https://stackoverflow.com/a/59812588
ENV PYTHONUNBUFFERED 1
# Makes a smaller docker image when installing modules?
ENV PYTHONDONTWRITEBYTECODE 1

# Install dependencies
RUN pip install --upgrade pip
COPY ./requirements.txt requirements.txt


RUN pip install -r requirements.txt


COPY setup.py setup.py
COPY pyparcel/__init__.py pyparcel/__init__.py
RUN pip install -e .

# There's probably a way to install everything at once but this works
COPY . usr/src/app

USER thalia
