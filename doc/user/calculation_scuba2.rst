SCUBA-2 Integration Time Calculator
===================================

This calculator can be used to estimate integration times for
`SCUBA-2 <http://www.eaobservatory.org/jcmt/instrumentation/continuum/scuba-2/>`_.

Source and Conditions
---------------------

You can either enter the declination of the source or give
an elevation or zenith angle.
If you enter the declination then the zenith angle
will be estimated as

.. math::
    angle_zenith = \cos^{-1}( 0.9 * \cos( dec - 19.823 ) )

where 19.823 is the latitude of the JCMT,
and the factor 0.9 is an approximation
for the average zenith angle of the source.

For the weather conditions you can either select one of the
`JCMT weather bands <http://www.eaobservatory.org/jcmt/observing/weather-bands/>`_,
in which case a representative value for that band will be used,
or select "Other" and enter a 225 GHz opacity value directly.

Observation
-----------

For the map type, select the
`SCUBA-2 observing mode <http://www.eaobservatory.org/jcmt/instrumentation/continuum/scuba-2/observing-modes/>`_
which you would like to use.

If you plan to use the matched filter, you should tick the
"Matched filter" box and the calculator will use
sampling factors appropriate for this filter
(:math:`f_850 = 5` and :math:`f_450=8` --- please see the
`SCUBA-2 sensitivity page <http://www.eaobservatory.org/jcmt/instrumentation/continuum/scuba-2/time-and-sensitivity/>`_
for more information).
Otherwise enter the pixel sizes you intend to use.

Requirement
-----------

The calculator has two modes:

Time required for RMS
  In this mode you can enter your desired sensitivity
  (:math:`1 \sigma` RMS in mJy/beam) and the wavelength.
  The calculator will estimate the time required to reach
  this sensitivity and will also show the sensitivity
  which would be reached in this time at SCUBA-2's other wavelength.

RMS expected in given time
  In this mode you can enter the total observing time in hours.
  The calculator will estimate the sensitivity which would
  be achieved in each of SCUBA-2's wavelengths.

You can change calculation mode by selecting the desired mode
in the "Calculator Mode" section and pressing the "Change mode"
button.
The calculator will attempt to adjust your inputs to
do the same calculation in the new mode.

.. image:: image/calc_scuba2_input_small.png
    :target: image/calc_scuba2_input_large.png
