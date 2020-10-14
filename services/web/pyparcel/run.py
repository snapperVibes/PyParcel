#!/usr/bin/env python3
import json
import sys
import time
import traceback
from datetime import timedelta
from typing import Optional, Dict, Any

import psycopg2

import pyparcel.fetch as fetch
import pyparcel.update as update
from pyparcel.common import DASHES, DB_URI, Tally


def _summarize(error) -> dict:
    summary = {}
    if error:
        summary["success"] = False
    else:
        summary["success"] = True
    summary["people updated"] = Tally.total
    summary["municipalities updated"] = Tally.muni_count
    return summary


# Make sure to update the module http_server if the function signature is changed
def _read_config(config: str) -> Dict[str, Any]:
    """

    Args:
        config: The string literal 'test' or 'production',
        based on which database should be connected to.

    Returns:
        The database, port, username, and password to connect to the postgresql server.

    Raises: ValueError
    """
    if config not in ["test", "production"]:
        raise ValueError("config must be either 'test' or 'production'")
    with open("secrets.json", "r") as f:
        secrets = json.load(f)
    return secrets[config]


def pyparcel(
    municode: Optional[str] = None,
    config: str = "test",
    each: bool = False,
    diff: bool = False,
    parcel: Optional[str] = None,
    commit: bool = False,
) -> dict:
    """

    Args:
        municode:
            Municipality municodes to update.
            Updates all municipalities if given an empty tuple.
            Defaults to updating all municipalities.
        config:

            Value must be 'test' or 'production'
        each:
            When true, update each parcel in each given municipality.
            Cannot be true if --parcels is true.
            Defaults false.
        diff:
            Search municipalities for parcels in the CoG database not in the WPRDC api.
            Checks missing parcels against the Allegheny County Real Estate Portal.
            Writes a NotInRealEstatePortal or DifferentMunicode event to the CoG database based on findings.
            Cannot be true if --parcels is true.
            Defaults false.
        parcel:
            Parcel to update.
            Cannot be true if --diff or --each is true
            If given an empty tuple:
                Updates ALL parcels in the municipalities set in --municodes
            Defaults to an empty tuple.
        commit:
            Whether the data should be committed to the database.
            Defaults false for testing purposes.

    Returns:
        Dictionary containing whether the operation was completed
        and the number of people / municipalities updated.
        Keys:
            "success": bool
            "people updated": int
            "municipalities updated": int
    """
    start = time.time()
    error = None
    try:
        # Simple validation. If an argument hasn't been provided, don't do anything.
        if any in [parcel, each, diff]:
            pass
        else:
            raise RuntimeError("Please provide the runtime argument 'parcel' or "
                               "either/both of 'each' or 'diff'.")

        if config == "test":
            print("Connected to the testing server.")
        elif config == "production":
            print("Connected to the production server.")

        if commit:
            print("Data will be committed to the database")
            # raise RuntimeError("Lorem Ipsum: Code is not production ready")
        else:
            print("Data will NOT be committed.")
        # print("Port = {}".format(secrets["port"]))
        print(DASHES)

        with psycopg2.connect(DB_URI) as conn:
            with conn.cursor() as cursor:

                if parcel:
                    if each or diff:
                        raise ValueError(
                            "--parcel cannot be passed alongside --each or --diff"
                        )
                    update.parcel(conn, cursor, commit, parid=parcel)

                # Give the option to iterate over ALL municipalities
                if municode is None:
                    municodes = [muni for muni in fetch.munis(cursor)]
                else:
                    municodes = [municode]

                for _municode in municodes:
                    muni = fetch.muniname_given_municode(_municode, cursor)
                    records = fetch.municipality_records_from_Wprdc(muni)

                    # Skip muni if the records are invalid
                    # (for example, for the test muni COG Land),
                    if not records:
                        print(
                            "Skipping {}: JSON does not contain records".format(
                                muni.name
                            )
                        )
                        print(DASHES)
                        continue

                    if each:
                        for record in records:
                            update.parcel(conn, cursor, commit, record=record)
                        print(DASHES)

                    if diff:
                        update.create_events_for_parcels_in_db_but_not_in_records(
                            records, muni.municode, conn, cursor, commit
                        )
                        print(DASHES)

                    Tally.muni_count += 1
                    print("Updated {} municipalities.".format(Tally.muni_count))
                    print(DASHES)

    except Exception:
        # Catches exceptions to be passed to the summery
        traceback.print_exc(limit=2, file=sys.stdout)
        error = True

    finally:
        try:
            print("Current muni {}:".format(muni.name))
        except NameError:
            pass
        end = time.time()
        summery = _summarize(error)
        print(
            "Total time: {}".format(
                # Strips milliseconds from elapsed time
                str(timedelta(seconds=(end - start))).split(".")[0]
            )
        )

        return summery


if __name__ == "__main__":
    print(
        "Did you mean to call this directly? "
        "If so, edit this code so it has your intended functionality."
    )
