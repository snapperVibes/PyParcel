from typing import Optional

import pyparcel.create as create
import pyparcel.events as events
import pyparcel.fetch as fetch
import pyparcel.parse as parse
import pyparcel.scrape as scrape
import pyparcel.write as write
from pyparcel.common import DEFAULT_PROP_UNIT
from pyparcel.common import SHORT_DASHES
from pyparcel.common import Tally


def _parcel_not_in_db(parid, cursor):
    select_sql = """
        SELECT parid FROM property
        WHERE parid = %s"""
    cursor.execute(select_sql, [parid])
    row = cursor.fetchone()
    if row is None:
        print("Parcel {} not in properties.".format(parid))
        return True
    return False


def _compare(WPRDC_data, AlleghenyCountyData):
    if WPRDC_data != AlleghenyCountyData:
        raise ValueError(
            "The WPRDC's data does not match the data scraped from Allegheny County\n"
            f"\t WPRDC's: {WPRDC_data}\tCounty's: {AlleghenyCountyData}"
        )


# Todo: Validate more data
def _validate_data(r, tax):
    #                                       #   WPRDC               Allegheny County
    _compare(r["TAXYEAR"], int(tax.year))  # #   2020.0              2020
    # TODO: Validate Use Code
    #   There was a particular parcel whose ID I lost that had a USE Code I don't remember seeing in the WPRDC data
    #   The Allegheny county real estate portal labeled it something like Rail Road


def parcel(
    conn,
    cursor,
    commit: bool,
    parid: Optional[str] = None,
    record: Optional[dict] = None,
):
    """

    Args:
        conn: The database connection
        cursor: The cursor of the database connection
        commit:
            True if data should be committed to the database,
            false if you're running tests
        parid: The parcel id to be updated. Cannot be choosen alongside record
        record: The WPRDC record representing the parcel. Cannot be choosen alongside parcel
    """
    # Validate parameters
    if record and parid:
        raise ValueError(
            "Function was passed both a parcel's id and WPRDC record. "
            "Choose one or the other"
        )
    if record:
        parid = record["PARID"]
    elif parid:
        record = fetch.record_using_parid(parid)
    else:
        raise ValueError(
            "Function was passed without an argument indicating "
            "the parcel's id or WPRDC record."
        )

    html = scrape.county_property_assessment(parid)
    soup = parse.soupify_html(html)
    owner_name = parse.OwnerName.from_soup(soup)
    tax_status = parse.parse_tax_from_soup(soup)

    if _parcel_not_in_db(parid, cursor):
        new_parcel = True
        imap = create.property_insertmap(record)
        prop_id = write.property(imap, cursor)
        #
        if record["PROPERTYUNIT"] == " ":
            unit_num = DEFAULT_PROP_UNIT
        else:
            unit_num = record["PROPERTYUNIT"]
        unit_id = write.unit(
            {"unitnumber": unit_num, "property_propertyid": prop_id}, cursor
        )
        #
        cecase_map = create.cecase_imap(prop_id, unit_id)
        cecase_id = write.cecase(cecase_map, cursor)
        #
        owner_map = create.owner_imap(owner_name, record)
        person_id = write.person(owner_map, cursor)
        #
        write.connect_property_to_person(prop_id, person_id, cursor)
        Tally.inserted += 1
    else:  # If the parcel was already in the database
        new_parcel = False
        prop_id = fetch.prop_id(parid, cursor)
        # If a property doesn't have an associated unit and cecase, one is created.
        unit_id = fetch.unit_id(prop_id, cursor)
        cecase_id = fetch.cecase_id(prop_id, cursor)

    _validate_data(record, tax_status)
    tax_status_id = write.taxstatus(tax_status, cursor)
    propextern_map = create.propertyexternaldata_imap(
        prop_id, owner_name.raw, record, tax_status_id
    )
    # Property external data is a misnomer.
    # It's just a log of the data from every time stuff
    write.propertyexternaldata(propextern_map, cursor)

    if events.query_propertyexternaldata_for_changes_and_write_events(
        parid, prop_id, cecase_id, new_parcel, cursor
    ):
        Tally.updated += 1

    if commit:
        conn.commit()
    else:
        # A check to make sure variables weren't forgotten to be assigned.
        # Maybe move to testing suite?
        assert [
            attr is not None
            for attr in [parid, new_parcel, prop_id, unit_id, cecase_id]
        ]

    # # A set of calls to quickly create mocks. Uncomment when needed 😛
    # from utils import pickler
    # pickler(record, "record", to_type="json", incr=False)
    # pickler(html, "html", to_type="html", incr=True)
    # pickler(owner_name, "own", incr=False)
    # pickler(soup, "soup", incr=False)
    # pickler(imap, "prop_imap", incr=False)
    # pickler(cecase_map, "cecase_imap", incr=False)
    # pickler(owner_map, "owner_imap", incr=False)
    # pickler(propextern_map, "propext_imap", incr=True)

    Tally.total += 1
    print("Record count:", Tally.total, sep="\t")
    print("Inserted count:", Tally.inserted, sep="\t")
    print("Updated count:", Tally.updated, sep="\t")
    print(SHORT_DASHES)


# Todo: rename method so it doesn't start with "create"
def create_events_for_parcels_in_db_but_not_in_records(
    records, municdode, db_conn, cursor, commit
):
    """
    Writes an event to the database for every parcel in a municipality that appears in the database but was not in the WPRDC's data.
    If a property doesn't have an associated unit and cecase, one is created.
    """
    # TODO: The current implementation creates an event multiple times if no change is made by the next month. Fix.
    # Get parcels in the database but not in the WPRDC record
    db_parcels = fetch.all_parids_in_muni(municdode, cursor)
    wprdc_parcels = [r["PARID"] for r in records]
    extra_parcels = set(db_parcels) - set(wprdc_parcels)
    for parcel_id in extra_parcels:
        prop_id = fetch.prop_id(parcel_id, cursor)
        cecase_id = fetch.cecase_id(prop_id, cursor)
        details = events.EventDetails(parcel_id, prop_id, cecase_id, cursor)
        details.old = municdode
        # Creates DifferentMunicode or NotInRealEstatePortal
        # If DifferentMunicode, supplies the new muni
        event = events.parcel_not_in_wprdc_data(details)
        event.write_to_db()
        Tally.diff_count += 1
    if commit:
        # db_conn.execute()
        db_conn.commit()
