# PyParcel
<!-- Keep the tagline up to date with the description in setup.py -->
###### A backend application for keeping the Turtle Creek COG's CodeNForce database up to date.
## Code Overview
**Soon to be implemented**

PyParcel can be called from the CodeNForce website or the command line.
Code Enforcement Officers can update an individual parcel or a whole municipality by clicking **LOREM IMPSUM**.

## For Developers

### Maintaining the code
#### How to add a new Event Category
* Add the new event category to the database. See example sql below.
  ~~~{caption="Example insert sql"}  
  INSERT INTO public.eventcategory(
           categoryid, categorytype, title, description, notifymonitors,
           hidable, icon_iconid, relativeorderwithintype, relativeorderglobal,
           hosteventdescriptionsuggtext, directive_directiveid, defaultdurationmins,
           active, userrankminimumtoenact, userrankminimumtoview, userrankminimumtoupdate)
   VALUES (?, 'PropertyInfoCase'::eventtype, '?', 'Documents ?', ?,
           TRUE, NULL, 0, 0,
           NULL, NULL, 1,
           TRUE, 7, 3, 7);
  ~~~
* Create a class corresponding to the event category in events.py. Make sure it inherits from the base class event. Make sure its name matches up exactly to the name in the database.
* **If the event is classified as a [Parcel Change](#parcel-change):**
  * Add a check for your flag in the function events.query_propertyexternaldata_for_changes_and_write_events. The check should take the following form:
    ~~~
    if old[i] != new[i]:
        details.unpack(old[i], new[i])
        YourNewEvent(details).write_to_db()
    ~~~
   
  * Add your event to the list parcel_changed_events in tests/test_pyparcel.py
    ~~~
    # A manually maintained list of Parcel Changed Event categories
    parcel_changed_events = [
        PCE(YourEvent, "Example starting data" "Example new data",
        ...
    ~~~
    The parametrization takes care of running the tests.


<h5 id=parcel-change>What constitutes a Parcel Change?</h5>
A regular, month to month change.
Examples include DifferentTaxStatus and DifferentOwner, but do not include events such as NewParcelid and ParcelNotInWprdcData.

### Mocking Event Initialization (For Testing)
Sometimes, your new Event contains setup code that causes the automatic testing of your event to fail.
Creating a custom mocked patch is easy: add your patch to `TestsRequiringADatabaseConnection.TestEventCategories.patches` using the provided format.
```
patches = [
    ...,
    PatchMaker(
        production_class=pyparcel.events.YourNewEvent,
        method="method_to_mock",
        return_value="return_value"
    )
]
```
The method `setup_mocks` then automatically adds your patch to a stack of context managers.
