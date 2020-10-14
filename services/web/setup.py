# Learn more about setup.py: https://github.com/kennethreitz/setup.py
import os
from codecs import open
from setuptools import setup, find_packages

import pdb
requires = ["requests", "psycopg2-binary", "beautifulsoup4", "colorama", "Flask"]
extras_requires = {"dev": ["pytest", "pre-commit", "black",]}

HERE = os.path.abspath(os.path.dirname(__file__))

# I put __init__.py in the same folder for docker images; Todo: Make sensible
# try:
with open(os.path.join(HERE, "pyparcel", "__init__.py"), "r", "utf-8") as f:
    exec(f.read(), about := {})
# except FileNotFoundError:
#     with open(os.path.join(HERE, "__init__.py"), "r", "utf-8") as f:
#         exec(f.read(), about := {})

# Keep description up to date with the README's tag line
description = "A backend application for " \
              "keeping the Turtle Creek COG's CodeNForce database up to date."

setup(
    name=about["__name__"],
    version=about["__version__"],
    description=description,
    long_description=description,
    author=about["__author__"],
    author_email=about["__email__"],
    python_requires=">=3.8",
    # url="https://github.com/TechnologyRediscovery/pyparcel",
    packages=find_packages(
        exclude=["tests", "*.tests", "*.tests.*", "tests.*", "parcelidlists"]
    ),
    py_modules=["pyparcel",],
    install_requires=requires,
    extras_require=extras_requires,
    include_package_data=True,
    license="GNU GENERAL PUBLIC LICENSE",
)
