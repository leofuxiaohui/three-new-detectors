import os
import pytest
from mock import patch
from mockito import mock, verify
from datetime import datetime, timezone, timedelta
from dateutil import parser
import pytz
import regions_recon_lambda.slips_email.slips_email as slips
from regions_recon_lambda.utils.dynamo_query import DynamoQuery


LOWER_LIMIT = parser.parse('2020-05-01T00:00:00').replace(tzinfo=pytz.UTC)


@pytest.fixture
def buildables():
    return mock(DynamoQuery, strict=True)


@pytest.mark.parametrize("items, unlaunched, expected", [
    ( [ ], [ ], [ ] ),
    (
        [ { }, { 'belongs_to_instance': 'ABC' }, { 'belongs_to_instance': '' }, { 'belongs_to_instance': 'DEF' } ],
        [ ],
        [ { }, { 'belongs_to_instance': 'ABC' }, { 'belongs_to_instance': '' }, { 'belongs_to_instance': 'DEF' } ]
    ),
    (
        [ { }, { 'belongs_to_instance': 'ABC' }, { 'belongs_to_instance': '' }, { 'belongs_to_instance': 'DEF' } ],
        [ 'ABC', 'DEF' ],
        [ { }, { 'belongs_to_instance': '' } ]
    ),
    (
        [ { 'belongs_to_instance': 'ABC' }, { 'belongs_to_instance': 'DEF' } ],
        [ 'FOO', 'BAR' ],
        [ { 'belongs_to_instance': 'ABC' }, { 'belongs_to_instance': 'DEF' } ]
    ),
    (
        [ { 'belongs_to_instance': 'ABC' }, { 'belongs_to_instance': 'DEF' } ],
        [ 'DEF', 'FUBAR' ],
        [ { 'belongs_to_instance': 'ABC' } ]
    )
])
def test_remove_unlaunched_regions(items, unlaunched, expected):
    assert slips.remove_unlaunched_regions(items, unlaunched) == expected


@pytest.mark.parametrize("plans, all_regions, expected_noplan", [
    ( [ ],                                               [ ],                     [ ] ),        # nothing begats nothing
    ( [ { 'region': 'ABC' } ],                           [ 'ABC' ],               [ 'ABC' ] ),  # no attributes
    ( [ { 'region': 'ABC', 'status': 'GA' } ],           [ 'ABC' ],               [ ]       ),  # status=GA means remove it from noplan
    ( [ { 'region': 'ABC', 'status': 'zz' } ],           [ 'ABC' ],               [ 'ABC' ] ),  # Bad status means keep it
    ( [ { 'region': 'ABC', 'confidence': 'Complete' } ], [ 'ABC' ],               [ ]       ),  # Good confidence means remove it
    ( [ { 'region': 'ABC', 'confidence': 'nope' } ],     [ 'ABC' ],               [ 'ABC' ] ),  # Bad confidence means keep it
    ( [ { 'region': 'ABC', 'date': '' } ],               [ 'ABC' ],               [ ]       ),  # Remove for any date value
    ( [ { 'region': 'ABC', 'date': 'nope' } ],           [ 'ABC' ],               [ ]       ),  # Remove for any date value
    ( [ { 'region': 'ABC', 'date': None } ],             [ 'ABC' ],               [ ]       ),  # Remove for any date value
    ( [ { 'region': 'ABC', 'status': 'GA' } ],           [ 'DEF' ],               [ 'DEF' ] ),  # Region isn't in region_list
    ( [ { 'region': 'ABC', 'status': 'GA' } ],           [ ],                     [ ]       ),  # No region_list
    ( [ { 'region': 'ABC', 'status': 'GA' } ],           [ 'ABC', 'DEF', 'GHI' ], [ 'DEF', 'GHI' ] ),
    ( [ ],                                               [ 'ABC', 'DEF', 'GHI' ], [ 'ABC', 'DEF', 'GHI' ] )
])
def test_populate_noplan(plans, all_regions, expected_noplan):
    services = {
        "fubar_service": {
            'regions': { plan['region']: { "0": plan }  for plan in plans },
            'noplan': []
        }
    }
    slips.populate_noplan(services, all_regions)
    assert services['fubar_service']['noplan'] == expected_noplan


@pytest.mark.parametrize("noplan, region_notes, expected_has_notes", [
    ( [ ],       { },                            False ),   # all regions have plans means has_notes==False
    ( [ ],       { 'ABC': True,  'DEF': True  }, False ),   # doesn't matter, no 'noplan' regions
    ( [ 'ABC' ], { 'ABC': True,  'DEF': False }, True  ),
    ( [ 'ABC' ], { 'ABC': False, 'DEF': True  }, False ),
    (
        [ 'ABC', 'DEF', 'GHI' ],
        { 'ABC': False, 'DEF': True, 'GHI': False  },  # any one is sufficient to be True
        True
    ),
    (
        [ 'ABC', 'DEF', 'GHI' ],
        { 'ABC': False, 'DEF': False, 'GHI': False  },
        False
    ),
])
def test_populate_has_notes(noplan, region_notes, expected_has_notes):
    services = {
        "fubar": {
            'noplan': noplan,
            'regions': {},
            'has_notes': False
        }
    }
    for region, note in region_notes.items():
        if note:
            services['fubar']['regions'][region] = { '0': { 'note': 'mynote' } }
        else:
            services['fubar']['regions'][region] = { '0': { 'not_a_note': '?' } }

    all_regions = [ 'ABC', 'DEF' ]
    slips.populate_has_notes(services, all_regions)
    assert services['fubar']['has_notes'] == expected_has_notes


def test_create_slips_improvements():
    def dt(s):
        return parser.parse(s).replace(tzinfo=pytz.UTC)

    services = {
        "foobar": {
            'metadata': { '0': { 'name_pretty': 'FooBar' } },
            'regions': {
                'AAA': { # only has a single entry, shouldn't appear in result
                    '0': dict(date=dt('2020-01-06'), updated=dt('2020-05-05'), updater='joe')
                },
                'BBB': { # has multiple entries, but is missing the immediate predecessor entry
                    '0': dict(date=dt('2020-01-06'), version_latest=6, updated=dt('2020-05-05'), updater='joe'),
                    '4': dict(date=dt('2020-01-02'), version_latest=6, updated=dt('2020-05-05'), updater='joe')
                },
                'CCC': { # has multiple entries, predecessor lacks a date field
                    '0': dict(date=dt('2020-01-06'), version_latest=6, updated=dt('2020-05-05'), updater='joe'),
                    '5': dict(                   version_latest=6, updated=dt('2020-05-05'), updater='joe')
                },
                'DDD': { # diff of current and previous is within the delta, so skip it
                    '0': dict(date=dt('2020-01-06'), version_latest=6, updated=dt('2020-05-05'), updater='joe'),
                    '5': dict(date=dt('2020-01-26'), version_latest=6, updated=dt('2020-05-05'), updater='joe')
                },
                'EEE': { # diff over delta, IMPROVEMENT
                    '0': dict(date=dt('2020-01-06'), version_latest=6, updated=dt('2020-05-05'), updater='joe'),
                    '5': dict(date=dt('2020-02-13'), version_latest=6, updated=dt('2020-05-05'), updater='joe')
                },
            }
        },
        "wibble": {
            'metadata': { '0': { 'name_pretty': 'Wibble' } },
            'regions': {
                'AAA': { # diff of current and previous is within the delta, so skip it
                    '0': dict(date=dt('2020-01-26'), version_latest=6, updated=dt('2020-05-05'), updater='joe'),
                    '5': dict(date=dt('2020-01-06'), version_latest=6, updated=dt('2020-05-05'), updater='joe')
                },
                'BBB': { # diff less than delta, SLIP
                    '0': dict(date=dt('2020-02-13'), version_latest=6, updated=dt('2020-05-05'), updater='joe'),
                    '5': dict(date=dt('2020-01-06'), version_latest=6, updated=dt('2020-05-05'), updater='joe')
                },
                'ZZZ': { # Region isn't in all_regions, should be ignored!
                    '0': dict(date=dt('2020-02-13'), version_latest=6, updated=dt('2020-05-05'), updater='joe'),
                    '5': dict(date=dt('2020-01-06'), version_latest=6, updated=dt('2020-05-05'), updater='joe')
                }
            }
        }
    }
    all_regions = [ 'AAA', 'BBB', 'CCC', 'DDD', 'EEE' ]
    ret_slips, ret_imprv = slips.create_slips_improvements(services, all_regions)
    assert len(ret_slips) == 1
    assert ret_slips[0]['name_rip'] == 'wibble'
    assert ret_slips[0]['region'] == 'BBB'
    assert ret_slips[0]['change'] == 38 # Feb 13 minus Jan 6th
    assert ret_slips[0]['name_pretty'] == 'Wibble'

    assert len(ret_imprv) == 1
    assert ret_imprv[0]['name_rip'] == 'foobar'
    assert ret_imprv[0]['region'] == 'EEE'
    assert ret_imprv[0]['change'] == 38 # Feb 13 minus Jan 6th
    assert ret_imprv[0]['name_pretty'] == 'FooBar'

def test_create_slips_improvements_multiple_updates():
    def dt(s):
        return parser.parse(s).replace(tzinfo=pytz.UTC)

    # In one day the customer updated their date by a day and then by another 38 days
    services = {
        "foobar": {
            'metadata': { '0': { 'name_pretty': 'FooBar' } },
            'regions': {
                'AAA': {
                    '0': dict(date=dt('2020-02-13'), version_latest=3, updated=dt('2020-05-05'), updater='joe'),
                    '3': dict(date=dt('2020-02-13'), version_latest=3, updated=dt('2020-05-05'), updater='joe'),
                    '2': dict(date=dt('2020-01-06'), version_latest=3, updated=dt('2020-05-05'), updater='joe'),
                    '1': dict(date=dt('2020-01-05'), version_latest=3, updated=dt('2020-05-05'), updater='joe'),
                }
            }
        }
    }
    all_regions = ['AAA']

    ret_slips, ret_imprv = slips.create_slips_improvements(services, all_regions)

    assert len(ret_slips) == 1
    assert ret_slips[0]['name_rip'] == 'foobar'
    assert ret_slips[0]['region'] == 'AAA'
    assert ret_slips[0]['change'] == 39 # Feb 13 minus Jan 5th


def test_gather_unplanned_regions():
    def dt(s):
        return parser.parse(s).replace(tzinfo=pytz.UTC)

    services = {
        'foo': {
            # Nothing in 'noplan', so should be ignored
            'noplan': [ ]
        },
        'bar': {
            # No notes, so just lists regions by name without extra fields included
            'noplan': [ 'BBB', 'AAA' ], # should be sorted by gather_unplanned_regions
            'has_notes': False,
            'metadata': { '0': { 'name_pretty': 'BAR' } },
        },
        'baz': {
            # Lots of Notes so expect all fields in output
            'noplan': [ 'BBB', 'AAA' ], # should be sorted by gather_unplanned_regions
            'has_notes': True,
            'metadata': { '0': { 'name_pretty': 'BAZ' } },
            'regions': {
                'AAA': { '0': { 'note': 'note1', 'updated': dt('2020-02-03'), 'updater': 'joe' } },
                'BBB': { '0': { } }
            }
        }
    }
    all_regions = [ 'AAA', 'BBB', 'CCC', 'DDD', 'EEE' ]
    unplanned = slips.gather_unplanned_regions(services)
    expected = [
        {
            'has_notes': False,
            'name_pretty': 'BAR',
            'name_rip': 'bar',
            'regions': [
                { 'region': 'AAA', 'separator': ',' },
                { 'region': 'BBB', 'separator': '' }
            ]
        },
        {
            'has_notes': True,
            'name_pretty': 'BAZ',
            'name_rip': 'baz',
            'regions': [
                { 'region': 'AAA', 'note': 'note1', 'updated': '2020-02-03', 'updater': 'joe' },
                { 'region': 'BBB', 'note': None, 'updated': None, 'updater': None }
            ]
        }
    ]
    assert unplanned == expected


def test_create_mm_params():
    updated_cutoff = parser.parse('2020-05-06 07:08:09').replace(tzinfo=pytz.UTC)
    slip_list = [ 's1', 's2', 's3', 's4' ]
    imprv_list = [ 'i1', 'i2' ]
    unplanned_regions = [
        { 'name_pretty': 'BBB' },
        { 'name_pretty': 'AAA' },
        { 'name_pretty': 'CCC' }
    ]
    result = slips.create_mm_params(updated_cutoff, slip_list, imprv_list, unplanned_regions)
    assert result == {
        "beginning": '2020-05-06',
        "end": datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        "last_sent_date": '2020-05-06 07:08 UTC',
        "slip_delta": 30,
        "slips_exist": True,
        "slip_count": 4,
        "slips": slip_list,
        "improvements_exist": True,
        "improvement_count": 2,
        "improvements": imprv_list,
        "unplanned_count": 3,
        "unplanned": [ # different than above: these get sorted
            { 'name_pretty': 'AAA' },
            { 'name_pretty': 'BBB' },
            { 'name_pretty': 'CCC' }
        ]
    }


@patch.dict(os.environ, { 'MM_STAGE': 'beta', 'ACCOUNT_ID': '123' })
def test_send_to_messagemultiplexer(when):
    url = slips.get_mm_endpoint('beta')
    mm_mock = mock()
    when(slips).MessageMultiplexerHelper(endpoint=url, own_account_number='123').thenReturn(mm_mock)

    slips.send_to_messagemultiplexer('params')

    expected_params = { 'message_group_name': 'region-slips', 'params': '"params"' }
    verify(mm_mock).perform_operation(operation='send_message', params=expected_params, convert_message_group_name=True)


@pytest.mark.parametrize("root_obj, attr_chain, default_value, expected_return", [
    ( None, None, None, None ),
    ( None, None, 12, 12 ),
    ( "hi", None, 13, 13 ),
    ( "hi", [], 14, 14 ),
    ( { }, [ 'a' ], None, None ),
    ( { }, [ 'a' ], 15, 15 ),
    ( { 'a': 16 }, [ 'a' ], None, 16 ),
    ( { 'a': 16 }, [ 'b' ], None, None ),
    ( { 'a': { 'b': { 'c': { } } } }, [ 'a', 'b', 'c' ], None, { } ),
    ( { 'a': { 'b': { 'c': { } } } }, [ 'a', 'c', 'b' ], 17, 17 ),
    ( { 'a': { 'b': { 'c': { } } } }, [ 'a', 'b' ], 18, { 'c': { } } ),
    ( { 'a': { 'b': { 'c': { } } } }, [ 'a', 'b', 'c', 'd' ], 19, 19 )
])
def test_none_safe_get(root_obj, attr_chain, default_value, expected_return):
    assert slips.none_safe_get(root_obj, attr_chain, default_value) == expected_return


def test_find_lowest_version_added():
    mock_updates = {}
    assert slips.find_lowest_version_added(mock_updates) == None

    mock_updates = {
        "0": {},
        "1": {},
        "2": {},
    }
    assert slips.find_lowest_version_added(mock_updates) == 1

    mock_updates = {
        "0": {},
        "2": {},
    }
    assert slips.find_lowest_version_added(mock_updates) == 2
