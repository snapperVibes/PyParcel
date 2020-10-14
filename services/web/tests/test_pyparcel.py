"""
Unit tests for the parcelupdate package.

🛑 Under no circumstance should tests connect to the production database. 🛑

The test suite assumes you have an up to date local copy of cogdb database and writes test_data to the copy.
The database (as of August 2020) is not very large, so a subset of the data is not provided.
A link to database dumps can be provided to interested contributors.

See the readme for notes on style.

A major refactoring would do these tests well. I apologize in advanced;
Unlike the rest of the package, I cannot say I am proud of the quality of my work.
    ~ Snapper
"""
import contextlib
import json
import pickle
import sys
import warnings
from copy import copy
from dataclasses import dataclass
from os import path
from typing import Type, Any

import psycopg2
import pytest

import pyparcel

from pyparcel import update
from pyparcel import events  # Hacky way to test all events
from pyparcel import parse
from pyparcel import run
from pyparcel.common import DB_URI
from pyparcel.parse import TaxStatus


from unittest import mock
from unittest.mock import MagicMock, MagicMixin

HERE = path.abspath(path.dirname(__file__))
MOCKS = path.join(HERE, "mocks", "")  # Represents the path to the folder

# Generates a list of every eventcategory class in _events
event_categories = []
this_module = copy(sys.modules[__name__].__dict__)
events_dict = this_module["events"].__dict__
for k in events_dict:
    try:
        if issubclass(events_dict[k], events.Event):
            # Skip over base classes
            if events_dict[k].__name__ not in ("Event", "ParcelChangedEvent"):
                event_categories.append(events_dict[k])
    except TypeError:
        continue


class PCE:
    """
    Parcel Changed Event helper
    """

    def __init__(
        self, event: Type[events.ParcelChangedEvent], old: Any, new: Any,
    ):
        """
        Args:
            event: The actual event class
            old: Example data representing data passed to EventDetails.old. EventDetails are used to initialize an event
            new: Different example data representing data passed to EventDetails.new
        """
        self.event = event
        self.old = old
        self.new = new


class ParcelChangedCursor(MagicMixin):
    """ A mocked psycopg2 cursor
    """

    def __init__(self, *args, spec=True, **kwargs):
        """
        Args:
            *args: PCE (Parcel Changed Event) instances.
                If ParcelChangedCursor is initialized with a PCE,
                the new PCE's `new` data is added to self.new instead of the PCE's `old` data.
                This represents a change in the data written to a column of propertyexternaldata.
            **kw: Arguments passed to the MagicMixin
        """
        super().__init__(spec, *args, **kwargs)
        self.old = [_pce.old for _pce in parcel_changed_events]
        self.new = []
        # Todo: This is janky. Make it clean.
        for _pce in parcel_changed_events:
            if _pce not in [*args]:
                self.new.append(_pce.old)
            else:
                self.new.append(_pce.new)

    def execute(self, *args):
        return None

    def fetchall(self):
        """ Represents events.query_propertyexternaldata_for_changes_and_write_events sql's returned value.
        """
        return [self.new, self.old]

    def fetchone(self):
        return [True]


# A manually maintained list of Parcel Changed Event categories
parcel_changed_events = [
    PCE(events.DifferentOwner, '{"OWNER OLD     "}', '{"OWNER NEW     "}'),
    PCE(events.DifferentStreet, "0 Old St ", "0 New St "),
    PCE(events.DifferentCityStateZip, "OLDCITY PA 12345", "NEWCITY PA 00000"),
    PCE(events.DifferentLivingArea, 1000, 2600),
    PCE(events.DifferentCondition, 8, 1),
    # PCE(events.DifferentMunicode, 653, 639)
]


@dataclass
class PatchMaker:
    """
    Sometimes you need to mock a method after creating a new Event Category
    Creating a custom mocked patch is easy: add your patch to `TestsRequiringADatabaseConnection.TestEventCategories.patches` using the provided format.
    The method `setup_mocks` then automatically adds your patch to a stack of context managers.

    Deprecate this class after finding a more Pythonic way to implement
    """

    production_class: Any  # Todo: Correct typing
    method: str
    return_value: Any


@pytest.fixture
def taxstatus_paid():
    return TaxStatus(
        year="2020",
        paidstatus="PAID",
        tax="473",
        penalty="000",
        interest="000",
        total="473",
        date_paid="6/2/2020",
    )


@pytest.fixture
def taxstatus_unpaid():
    return TaxStatus(
        year="2020",
        paidstatus="UNPAID",
        tax="36894",
        penalty="1845",
        interest="369",
        total="39108",
        date_paid=None,
    )


@pytest.fixture
def taxstatus_balancedue():
    return TaxStatus(
        year="2020",
        paidstatus="BALANCE DUE",
        tax="069",
        penalty="003",
        interest="001",
        total="073",
        date_paid=None,
    )


@pytest.fixture
def taxstatus_none():
    return TaxStatus(
        year="2020",
        paidstatus=None,
        tax="000",
        penalty="000",
        interest="000",
        total="000",
        date_paid=None,
    )


class TestEventTriggers:
    """ These tests ensure that an event calls write_to_db when it is supposed to
    """

    # Todo: Test the test (call with parameters that will not trigger assert called once)
    @pytest.mark.parametrize("pce", parcel_changed_events)
    def test_property_external_data(self, pce):
        """
        Test events.query_propertyexternaldata_for_changes_and_write_events calls write_to_db
        whenever there is a difference in selection data.
        """
        event = pce.event
        with mock.patch.object(event, "write_to_db"):
            mocked_cursor = ParcelChangedCursor(pce)
            events.query_propertyexternaldata_for_changes_and_write_events(
                parid=None,
                prop_id=None,
                cecase_id=None,
                new_parcel=None,
                db_cursor=mocked_cursor,
            )
            event.write_to_db.assert_called_once()

    def test_multiple_propertyexternaldata_events(self):
        """ This test ensures that a cursor triggering multiple events actually result in writing multiple events.
        """
        # Sets up a cursor where EVERY event has a change in data
        patches = []
        for pce in parcel_changed_events:
            event = pce.event
            patch = mock.patch.object(event, "write_to_db")
            patches.append(patch)
            patch.start()
        mocked_cursor = ParcelChangedCursor(*[pce for pce in parcel_changed_events])

        # The actual "act" of testing. Everything else is arrange and assert.
        events.query_propertyexternaldata_for_changes_and_write_events(
            parid=None,
            prop_id=None,
            cecase_id=None,
            new_parcel=None,
            db_cursor=mocked_cursor,
        )

        for pce, patch in zip(parcel_changed_events, patches):
            event = pce.event
            event.write_to_db.assert_called_once()
            event.write_to_db.reset_mock()
            patch.stop()

    @mock.patch(
        "pyparcel.events.parse.Municipality.from_raw",
        return_value=parse.Municipality(999, "COGLand"),
    )
    @mock.patch("pyparcel.events.scrape.county_property_assessment",)
    @mock.patch("pyparcel.events.parse.validate_county_municode_against_portal")
    def test_parcel_not_in_wprdc_data_DifferentMunicode(self, m1, m2, m3):
        event = events.parcel_not_in_wprdc_data(MagicMock())
        assert isinstance(event, events.DifferentMunicode)

    @mock.patch("pyparcel.events.scrape.county_property_assessment")
    @mock.patch("pyparcel.events.parse.validate_county_municode_against_portal", return_value=[])
    def test_parcel_not_in_wprdc_data_NotInRealEstatePortal(
        self, m1, m2,
    ):
        event = events.parcel_not_in_wprdc_data(MagicMock())
        assert isinstance(event, events.NotInRealEstatePortal)


class TestParse:
    class TestParseTaxFromSoup:
        """ Assert parse_tax_from_soup returns the correct TaxStatus, given a BeautifulSoup object
        """

        def test_paid(self, taxstatus_paid):
            with open(MOCKS + "paid.pickle", "rb") as p:
                soup = pickle.load(p)
            assert parse.parse_tax_from_soup(soup) == taxstatus_paid

        def test_unpaid(self, taxstatus_unpaid):
            with open(MOCKS + "unpaid.pickle", "rb") as p:
                soup = pickle.load(p)
            assert parse.parse_tax_from_soup(soup) == taxstatus_unpaid

        def test_balancedue(self, taxstatus_balancedue):
            with open(MOCKS + "balancedue.pickle", "rb") as p:
                soup = pickle.load(p)
            assert parse.parse_tax_from_soup(soup) == taxstatus_balancedue

        def test_none(self, taxstatus_none):
            # Todo: Does the truly represent no taxes, or is it representative of blank data?
            with open(MOCKS + "none.pickle", "rb") as p:
                soup = pickle.load(p)
            assert parse.parse_tax_from_soup(soup) == taxstatus_none

    class TestParseOwnerFromSoup:
        pass


try:
    conn = psycopg2.connect(DB_URI)
except psycopg2.OperationalError:
    conn = MagicMock()
    warnings.warn(
        "A database connection could not be established. Skipping tests that require a connection."
    )



with conn:

    # def transaction(func):
    #     """ transaction is a decorator that allows each unittest to be run in its own transaction
    #     """
    #
    #     @functools.wraps(func)
    #     def wrapper(*args, **kwargs):
    #         cursor = conn.cursor()
    #         try:
    #             cursor.execute("BEGIN;")
    #             func(*args, **kwargs)
    #         finally:
    #             cursor.execute("ROLLBACK;")
    #             cursor.close()
    #
    #     return wrapper

    def db_connection_established():
        """ db_connection_established is a flag representing if a database connection could be made.
        """
        if isinstance(conn, psycopg2.extensions.connection):
            return True

    @pytest.mark.skipif(
        not db_connection_established(), reason="Requires a database connection"
    )
    class TestsRequiringADatabaseConnection:
        class TestWrites:
            """
            Instead of doing proper unit testing, we take the easy way out and write an integration test.
            We do not check that it wrote the correct data, as the methods used to create the insert maps are assumed to work.

            As of August 2020 the following functions write to the database (and are thus loosely covered by these tests):
                    write.property()
                    write.cecase()
                    write.person()
                    write.connect_property_to_person()
                    write.taxstatus()
                    write.propertyexternaldata()
            """

            # Todo: Convert to decorator
            def setup_mocks(self):
                with open(path.join(MOCKS, "record.json"), "r") as f:
                    mock_record = json.load(f)
                with open(path.join(MOCKS, "real_estate_portal.html"), "r") as f:
                    mocked_html = f.read()
                self.mock_record = mock_record
                self.mocked_html = mocked_html

            def test_update_parcel_given_record(self):
                self.setup_mocks()
                with conn.cursor() as cursor:
                    with mock.patch(
                        "pyparcel.update.fetch.record_using_parid",
                        return_value=self.mock_record,
                    ):
                        update.parcel(
                            conn,
                            cursor,
                            commit=False,
                            parid="0374R00210000000",
                            record=None,
                        )

            def test_update_parcel_given_parcel(self):
                self.setup_mocks()
                with conn.cursor() as cursor:
                    with mock.patch(
                        "pyparcel.update.scrape.county_property_assessment",
                        return_value=self.mocked_html,
                    ):
                        update.parcel(
                            conn,
                            cursor,
                            commit=False,
                            parid=None,
                            record=self.mock_record,
                        )

        class TestEventCategories:
            """ Ensures events in events.py share the same attributes of their counterpart in the database.
            """

            # Todo: HEAVY documentation.
            # Some events require mocked methods to be instantiated
            patches = [
                PatchMaker(
                    production_class=pyparcel.events.DifferentMunicode,
                    method="_extend_eventdescription",
                    return_value="",
                )
            ]

            @contextlib.contextmanager
            def setup_mocks(self):
                try:
                    stack = contextlib.ExitStack()
                    for _mock in self.patches:
                        stack.enter_context(
                            mock.patch.object(
                                _mock.production_class,
                                _mock.method,
                                return_value=_mock.return_value,
                            )
                        )
                    yield stack
                finally:
                    stack.close()

            @pytest.mark.parametrize("event", event_categories)
            def test_name_integrity(self, event):
                """ Compares the class's name to the database's event category's title.
                """
                with conn.cursor() as cursor:

                    with self.setup_mocks():
                        instance = event(MagicMock())  # Initialize event with no data
                        info = {}
                        info["category_id"] = instance.category_id
                        select_sql = """
                                    SELECT title
                                    FROM eventcategory
                                    WHERE categoryid = %(category_id)s;
                                    """
                        cursor.execute(select_sql, info)
                        row = cursor.fetchone()
                        assert event.__name__ == row[0]

            # Todo: Refactor
            @pytest.mark.parametrize("event", event_categories)
            def test_active_integrity(self, event):
                """ Compares the class's default active status to the database's.
                """
                with conn.cursor() as cursor:
                    with self.setup_mocks():
                        instance = event(MagicMock())
                        info = {}
                        info["category_id"] = instance.category_id
                        select_sql = """
                                SELECT active
                                FROM eventcategory
                                WHERE categoryid = %(category_id)s;
                                """
                        cursor.execute(select_sql, info)
                        row = cursor.fetchone()
                        assert instance.active == row[0]


if __name__ == "__main__":
    pytest.main()
