from unittest.mock import Mock, patch

import pytest
from regions_recon_python_common.buildables_dao_models.buildables_item import BuildablesItem
from regions_recon_python_common.buildables_dao_models.service_plan import ServicePlan

from regions_recon_lambda.rip_ingestor.model_converters import convert_buildable_region_to_model, \
    convert_buildable_service_metadata_to_model, convert_buildable_service_plan_to_model, is_service, \
    is_service_metadata, is_service_plan, _convert_buildable_item_to_versioned_model


@pytest.fixture
def mock_buildables_region():
    mock_buildables_region = Mock()
    mock_buildables_region.local_item = {
        "artifact": "REGION",
        "instance": "TST:v0",
        "version_instance": 0,
        "version_latest": 3
    }

    return mock_buildables_region


@pytest.fixture
def mock_buildables_service():
    mock_buildables_service = Mock()
    mock_buildables_service.local_item = {
        "artifact": "SERVICE",
        "instance": "test:v0",
        "version_instance": 0,
        "version_latest": 2,
        "plan": "TEST PLAN",
        "belongs_to_artifact": "SERVICE",
        "updating_agent": "TESTING"
    }

    return mock_buildables_service


@pytest.fixture
def mock_buildables_plan():
    mock_buildables_service = Mock()
    mock_buildables_service.local_item = {
        "artifact": "SERVICE",
        "instance": "test:v0:IAD",
        "version_instance": 0,
        "version_latest": 3,
        "plan": "TEST PLAN",
        "belongs_to_artifact": "SERVICE",
        "updater": "test",
        "updated": "2020-01-01T12:00:00",
        "updating_agent": "TESTING"
    }

    return mock_buildables_service


@pytest.fixture
def mock_previous_service_plan():
    return ServicePlan(artifact="SERVICE", instance="test:v0:IAD", updater="ven", _user_instantiated=False)


def test_convert_buildable_region_to_model(mock_buildables_region):
    with patch.object(BuildablesItem, 'get', lambda x, y: None):
        converted_item = convert_buildable_region_to_model(mock_buildables_region)

    assert converted_item.version_instance == 0
    assert not getattr(converted_item, "version_latest", None)


def test_convert_buildable_service_metadata_to_model(mock_buildables_service):
    with patch.object(BuildablesItem, 'get', lambda x, y: None):
        converted_item = convert_buildable_service_metadata_to_model(mock_buildables_service)

    assert converted_item.plan == "TEST PLAN"
    assert not getattr(converted_item, "belongs_to_artifact", None)


def test_convert_buildable_service_plan_to_model(mock_buildables_plan):
    with patch.object(BuildablesItem, 'get', lambda x, y: None):
        converted_item = convert_buildable_service_plan_to_model(mock_buildables_plan)

    assert converted_item.belongs_to_artifact == "SERVICE"


def test_convert_buildable_service_plan_to_model_without_previous_updater(mock_buildables_plan, mock_previous_service_plan):
    mock_previous_service_plan.updater = None

    with patch.object(BuildablesItem, 'get', lambda x, y: mock_previous_service_plan):
        converted_item = convert_buildable_service_plan_to_model(mock_buildables_plan)

    # without a previous updater value, we should change the updater to reflect the current updater
    assert converted_item.updater == mock_buildables_plan.local_item["updater"]


def test__convert_buildable_item_to_versioned_model_with_increment(mock_buildables_plan, mock_previous_service_plan):
    with patch.object(BuildablesItem, 'get', lambda x, y: mock_previous_service_plan):
        converted_item = _convert_buildable_item_to_versioned_model(mock_buildables_plan, ServicePlan)

    # with a previous updater, and an increment on version, we should see that updater changes to the current updater
    assert converted_item._get_items_to_write()[0].updater == mock_buildables_plan.local_item["updater"]


def test__convert_buildable_item_to_versioned_model_without_increment(mock_buildables_plan, mock_previous_service_plan):
    mock_previous_service_plan.test_plan = mock_buildables_plan.local_item['plan']
    with patch.object(BuildablesItem, 'get', lambda x, y: mock_previous_service_plan):
        converted_item = _convert_buildable_item_to_versioned_model(mock_buildables_plan, ServicePlan)

    # with a previous updater, and no increment on version, we should see that updater stays the same as the previous
    assert converted_item._get_items_to_write()[0].updater == mock_previous_service_plan.updater


def test_is_service(mock_buildables_region, mock_buildables_service):
    assert not is_service(mock_buildables_region)
    assert is_service(mock_buildables_service)


def test_is_service_metadata(mock_buildables_region, mock_buildables_service, mock_buildables_plan):
    assert not is_service_metadata(mock_buildables_region)
    assert is_service_metadata(mock_buildables_service)
    assert not is_service_metadata(mock_buildables_plan)


def test_is_service_plan(mock_buildables_region, mock_buildables_service, mock_buildables_plan):
    assert not is_service_plan(mock_buildables_region)
    assert not is_service_plan(mock_buildables_service)
    assert is_service_plan(mock_buildables_plan)
