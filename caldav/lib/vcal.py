#!/usr/bin/env python
# -*- encoding: utf-8 -*-
import datetime
import re
import uuid

from caldav.lib.python_utilities import to_normal_str

## Fixups to the icalendar data to work around compatbility issues.

## TODO:

## 1) this should only be done if needed.  Use try-except around the
## fragments where icalendar/vobject is parsing ical data, and do the
## fixups there.

## 2) arguably, this is outside the scope of the caldav library.
## check if this can be done in vobject or icalendar libraries instead
## of here

## TODO: would be nice with proper documentation on what systems are
## generating broken data.  Compatibility issues should also be collected
## in the documentation. somewhere.
def fix(event):
    """This function receives some ical as it's given from the server, checks for
    breakages with the standard, and attempts to fix up known issues:

    1) COMPLETED MUST be a datetime in UTC according to the RFC, but sometimes
    a date is given. (Google Calendar?)

    2) The RFC does not specify any range restrictions on the dates,
    but clearly it doesn't make sense with a CREATED-timestamp that is
    centuries or decades before RFC2445 was published in 1998.
    Apparently some calendar servers generate nonsensical CREATED
    timestamps while other calendar servers can't handle CREATED
    timestamps prior to 1970.  Probably it would make more sense to
    drop the CREATED line completely rather than moving it from the
    end of year 0AD to the beginning of year 1970. (Google Calendar)

    3) iCloud apparently duplicates the DTSTAMP property sometimes -
    keep the first DTSTAMP encountered (arguably the DTSTAMP with earliest value
    should be kept).

    4) ref https://github.com/python-caldav/caldav/issues/37,
    X-APPLE-STRUCTURED-EVENT attribute sometimes comes with trailing
    white space.  I've decided to remove all trailing spaces, since
    they seem to cause a traceback with vobject and those lines are
    simply ignored by icalendar.
    """
    ## TODO: add ^ before COMPLETED and CREATED?
    ## 1) Add a random time if completed is given as date
    fixed = re.sub(
        r"COMPLETED:(\d+)\s", r"COMPLETED:\g<1>T120000Z", to_normal_str(event)
    )

    ## 2) CREATED timestamps prior to epoch does not make sense,
    ## change from year 0001 to epoch.
    fixed = re.sub("CREATED:00001231T000000Z", "CREATED:19700101T000000Z", fixed)
    fixed = re.sub(r"\\+('\")", r"\1", fixed)

    ## 4) trailing whitespace probably never makes sense
    fixed = re.sub(" *$", "", fixed)

    ## 3 fix duplicated DTSTAMP
    ## OPTIMIZATION TODO: use list and join rather than concatination
    ## remove duplication of DTSTAMP
    fixed2 = ""
    for line in fixed.strip().split("\n"):
        if line.startswith("BEGIN:V"):
            cnt = 0
        if line.startswith("DTSTAMP:"):
            if not cnt:
                fixed2 += line + "\n"
            cnt += 1
        else:
            fixed2 += line + "\n"

    return fixed2


## sorry for being english-language-euro-centric ... fits rather perfectly as default language for me :-)
def create_ical(ical_fragment=None, objtype=None, language="en_DK", **props):
    """
    I somehow feel this fits more into the icalendar library than here
    """
    ## late import, icalendar is not an explicit requirement for v0.x of the caldav library.
    ## (perhaps I should change my position on that soon)
    import icalendar

    ical_fragment = to_normal_str(ical_fragment)
    if not ical_fragment or not re.search("^BEGIN:V", ical_fragment, re.MULTILINE):
        my_instance = icalendar.Calendar()
        my_instance.add("prodid", "-//python-caldav//caldav//" + language)
        my_instance.add("version", "2.0")
        if objtype is None:
            objtype = "VEVENT"
        component = icalendar.cal.component_factory[objtype]()
        component.add("dtstamp", datetime.datetime.now())
        component.add("uid", uuid.uuid1())
        my_instance.add_component(component)
    else:
        if not ical_fragment.startswith("BEGIN:VCALENDAR"):
            ical_fragment = (
                "BEGIN:VCALENDAR\n"
                + to_normal_str(ical_fragment.strip())
                + "\nEND:VCALENDAR\n"
            )
        my_instance = icalendar.Calendar.from_ical(ical_fragment)
        component = my_instance.subcomponents[0]
        ical_fragment = None
    for prop in props:
        if props[prop] is not None:
            if prop in ("child", "parent"):
                for value in props[prop]:
                    component.add(
                        "related-to", props[prop], parameters={"rel-type": prop.upper()}
                    )
            else:
                component.add(prop, props[prop])
    ret = to_normal_str(my_instance.to_ical())
    if ical_fragment and ical_fragment.strip():
        ret = re.sub(
            "^END:V", ical_fragment.strip() + "\nEND:V", ret, flags=re.MULTILINE
        )
    return ret
