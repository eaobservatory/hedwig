# Module to create extra features of modules which we "mock" to allow
# building of the documentation on systems without all the dependencies.
# This file only deals with modules for which Sphinx's autodoc_mock_imports
# feature doesn't suffice.

import sys

try:
    from unittest.mock import Mock
except ImportError:
    from mock import Mock

# For problematic modules, have Mock prepare them now so that we can
# adjust as necessary.
for modname in [
        'astropy', 'astropy.coordinates',
        'astropy.io', 'astropy.io.fits',
        'astropy.time', 'astropy.units', 'astropy.units.quantity',
        'astropy.utils.exceptions', 'astropy.utils.iers',
        'jcmt_itc_heterodyne',
        'jcmt_itc_heterodyne.receiver',
        'jcmt_itc_heterodyne.line_catalog',
        ]:
    sys.modules[modname] = Mock()

# Mock a "namedtuple" class which we extend at import time.
sys.modules['jcmt_itc_heterodyne.receiver'].ReceiverInfo = \
    type('ReceiverInfo', (), {'_fields': ()})
