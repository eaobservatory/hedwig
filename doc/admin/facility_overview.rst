Overview of Structures
======================

Preparing the system to accept proposals involves creating a number
of database structures.
This can be done from the facility's :doc:`administrative menu <menu>`.
The structures include:

Semesters
    A semester represents a period of observing time for which proposals
    are being sought.
    It is assumed that the state of the facility
    (e.g. available instrumentation)
    will be associated with the semester itself,
    so this can be recorded in the semester description.

Queues
    Each queue represents a channel through which applicants may submit
    proposals.
    In some cases a facility may only have one queue,
    but multiple queues would be used if, for example,
    applicants of different affiliations apply separately.

Calls
    A call is created by linking together a queue and a semester.
    The call also contains additional information such as the period
    of time during which the call is open for submissions.

These structures are illustrated in the diagram below.

.. graphviz:: graph/structure_relationship.dot

Additional Notes
----------------

* When a call is created, a particular call type is selected.
  This may alter the way proposals are handled --- for example
  proposals for urgent / immediate calls are sent for review immediately
  on submission rather than remaining editable until the call closing date.

* A preamble can be added to the semester description for each call type.
  This is a good place to describe the requirements of a particular call.

* Proposal member affiliations and reviewer groups are configured by queue.
  This allows the same information to be retained for multiple semesters.
