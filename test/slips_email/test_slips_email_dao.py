import pytest
from mockito import mock, ANY, verify
from dateutil import parser
import pytz
from freezegun import freeze_time
from regions_recon_lambda.slips_email.slips_email_dao import SlipsEmailDAO
from regions_recon_lambda.utils.dynamo_query import DynamoQuery


LOWER_LIMIT = parser.parse('2020-05-01T00:00:00').replace(tzinfo=pytz.UTC)


@pytest.fixture
def buildables():
    return mock(DynamoQuery, strict=True)


@pytest.fixture
def dao(buildables):
    dao = SlipsEmailDAO()
    dao.buildables = buildables
    return dao


@pytest.mark.parametrize("item, expected_return", [
    ( None, LOWER_LIMIT ),
    ( {}, LOWER_LIMIT ),
    ( { 'updated': None }, LOWER_LIMIT ),
    ( { 'updated': '' }, LOWER_LIMIT ),
    ( { 'updated': 'not-a-date!' }, LOWER_LIMIT ),
    ( { 'updated': '2019-12-25' }, LOWER_LIMIT ),
    ( { 'updated': '2020-04-30T00:00:00' }, LOWER_LIMIT ),
    ( { 'updated': '2020-05-02T00:00:00' }, parser.parse('2020-05-02T00:00:00').replace(tzinfo=pytz.UTC) )
])
def test_get_update_cutoff(item, expected_return, when, dao):
    when(dao.buildables).get_item('NOTIFICATION', 'region-slips', ['updated']).thenReturn(item)
    assert dao.get_update_cutoff(LOWER_LIMIT) == expected_return


@freeze_time("2020-01-02 03:04:05", tz_offset=0)
def test_set_update_cutoff(when, dao):
    when(dao.buildables).update_item(ANY, ANY, updated=ANY).thenReturn(123)
    dao.set_update_cutoff()
    verify(dao.buildables).update_item('NOTIFICATION', 'region-slips', updated="2020-01-02 03:04:05 UTC")


def test_get_unlaunched_regions_found(when, dao):
    item = dict(artifact='SERVICE', instance='foo:v56:bar', belongs_to_artifact='REGION', belongs_to_instance='bar', plan='myplan', updated='2020-08-08', updater='joe', version_instance=56, version_latest=64)
    when(dao.buildables).get_item('SERVICE', "foo:v56:bar").thenReturn(item)
    assert dao.get_plan("foo", 56, "bar") == item


def test_get_unlaunched_regions_notfound(when, dao):
    when(dao.buildables).get_item('SERVICE', "foo:v56:bar").thenReturn(None)
    assert dao.get_plan("foo", 56, "bar") is None


@pytest.mark.parametrize("items, expected_return", [
    ( [], [] ),
    ( [ { 'instance': 'A:v0' }, { 'instance': 'B:v0' }, { 'instance': 'C:v0' } ], [ 'A', 'B', 'C' ] )
])
def test_get_unlaunched_regions(items, expected_return, when, dao):
    when(dao.buildables).query(ANY, ANY, ANY, ANY).thenReturn(items)
    assert dao.get_unlaunched_regions() == expected_return


@pytest.mark.parametrize("items, expected_service, expected_plan", [
    ( [ ], [ ], [ ] ),
    (
        [ { 'name': 'A' }, { 'name': 'B' }, { 'name': 'C' } ],
        [ { 'name': 'A' }, { 'name': 'B' }, { 'name': 'C' } ],
        [ ]
    ),
    (
        [ { 'belongs_to_artifact': 'nope' }, { 'belongs_to_artifact': 'REGION' } ],
        [ { 'belongs_to_artifact': 'nope' } ],
        [ { 'belongs_to_artifact': 'REGION' } ]
    ),
    (
        [ { }, { 'name': 'A' }, { 'belongs_to_artifact': 'REGION' }, { 'name': 'B' }, { }, { 'belongs_to_artifact': 'nope' } ],
        [ { }, { 'name': 'A' }, { 'name': 'B' }, { }, { 'belongs_to_artifact': 'nope' } ],
        [ { 'belongs_to_artifact': 'REGION' } ]
    )
])
def test_get_services_and_plans(items, expected_service, expected_plan, when, dao):
    dao.should_validate = False
    when(dao.buildables).query(ANY, ANY, ANY, ANY).thenReturn(items)
    svc, pln = dao.get_services_and_plans()
    assert svc == expected_service
    assert pln == expected_plan
