# Module to create extra features of modules which we "mock" to allow
# building of the documentation on systems without all the dependencies.
# This file only deals with modules for which Sphinx's autodoc_mock_imports
# feature doesn't suffice.

from sphinx.ext.autodoc import mock_import

# For problematic modules, have Sphinx mock them now so that we can
# adjust as necessary.  (Otherwise Sphinx mocks them just before importing
# a module to document.)
for modname in [
        'jcmt_itc_heterodyne',
        'jcmt_itc_heterodyne.receiver',
        'PIL',
        'sqlalchemy',
        'sqlalchemy.engine',
        'sqlalchemy.exc',
        'sqlalchemy.pool',
        'sqlalchemy.sql',
        'sqlalchemy.sql.expression',
        'sqlalchemy.sql.functions',
        'sqlalchemy.schema',
        'sqlalchemy.types',
        ]:
    mock_import(modname)


# Mock module for SQLAlchemy schema and types since we construct the metadata
# on import, we need the entries of these modules to be returned as classes.
# Based on sphinx.ext.autodoc._MockModule.
class MockSQLAModule(object):
    @classmethod
    def __getattr__(cls, name):
        if name in ('__file__', '__path__'):
            return '/dev/null'
        return MockSQLAClass


class MockSQLAClass(object):
    columns = []

    def __init__(self, *args, **kwargs):
        pass


for modname in ['sqlalchemy.schema', 'sqlalchemy.types']:
    sys.modules[modname] = \
        type('', (MockSQLAModule, type(sys.modules[modname])), {})()


# Mock "enum" type classes where we use the enum values at import time.
class MockEnumClass(object):
    def __getattr__(cls, name):
        return None

sys.modules['PIL'].Image = MockEnumClass()
sys.modules['jcmt_itc_heterodyne'].HeterodyneITC = MockEnumClass()

# Mock a "namedtuple" class which we extend at import time.
sys.modules['jcmt_itc_heterodyne.receiver'].ReceiverInfo = \
    type('ReceiverInfo', (), {'_fields': ()})
