Target Objects
==============

To open the target object list editor,
click the "Edit targets" link in the "Target Objects"
section of your proposal.

You can use the "Add target" button to add as many rows
to the table as necessary.
The "Delete" button removes rows from the table,
but as always, your changes on this page are not
saved until you press the "Save" button at the bottom of the page.

The "Resolve name" button can be used to attempt to determine the
coordinates of an object from its name using CADC's Name Resolver.
If successful the RA and Dec columns will then be filled in for you,
otherwise you will need to enter these yourself.

Note also the "Time" and "Priority" columns.
These columns are useful for helping
the Time Allocation Committee to understand your proposal.
For example, if insufficient time is available for your
proposal to be accepted in its entirety,
the committee may be able to use the target priority information
to award sufficient time for a subset of your proposed project.

.. image:: image/target_edit.png

Uploading a list of Targets
---------------------------

As an alternative to entering target coordinates online,
you can upload a list as a text file (space or comma-separated).
The required format is explained on the upload page,
which you can reach using the "Upload target list"
link on your proposal.

Be sure to check or un-check the "Overwrite" option depending on
whether you want to replace any existing targets
(overwrite checked) or add targets to your existing list
(overwrite un-checked).

.. image:: image/target_upload.png

Clash Tool
----------

Once you have a list of targets attached to your proposal,
you can use the "Clash Tool" to check them for matches
against defined areas of the sky.
To use this tool, select
"Check targets: Clash Tool" in the "Target Objects"
section of your proposal.

You should see a list of "Matches"
(your target objects which fell within one of the defined sky areas)
and "Non-matches" (your target objects for which no search results were found).
In the case of a match, you can click on the name of the area
to see a description of it.

A warning will be shown if the Clash Tool is in the process of being updated.
If you see this warning, please be aware that the search results
may be incomplete ---
it is recommended that you return to the Clash Tool later to
repeat your search.

.. image:: image/target_clash.png

There is an area on your proposal where you can enter notes on the
results of the Clash Tool.
When you have added a list of target objects,
you will see a link "Edit note" in the "Target Objects" section
of the proposal.
Anyone viewing your proposal will be able to use the latest version
of the clash tool to check the target coordinates,
so you do not need to include the result of the tool here.
You should just include your comments about the results
--- this could be as simple as
"The clash tool did not find any matches"
if that is the case.


This note is particularly important when clashes are found ---
you can use this space to explain why you still need to observe
the corresponding targets.

.. image:: image/target_note.png

Target Availability
-------------------

Another tool which you can use to check your target objects
is the "Target Availability" tool,
which determines when during the semester they will be observable.
To use this tool, select
"Check targets: Target Availability" in the "Target Objects"
section of your proposal.

This tool shows two tables:

Availability by Date
    This table shows a series of times through a typical observing night
    and a series of dates through the semester.

    Each cell in the table indicates how many of your targets
    are observable at that date and time.

Availability by Target
    This table only appears if you have multiple targets.

    For each target, it shows approximately for
    how much of the time during the semester that target is available.
    This can allow you to identify targets for which
    a different semester might be a better choice.

.. image:: image/target_avail.png
