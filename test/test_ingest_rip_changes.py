import os
import pytest
import json
import unittest.mock

from regions_recon_python_common.buildables_dao_models.buildables_item import BuildablesItem

from regions_recon_lambda.ingest_rip_changes import ingest_rip_changes, RipChangesIngestor, parent_object_exists, \
    is_in_list_of_ignored_services, validate_region_item
from regions_recon_python_common.buildable_item import BuildableService, BuildableRegion
from regions_recon_lambda.rip_message_record import RipMessageRecord
from unittest.mock import Mock

os.environ["BUILDABLES_TABLE_NAME"] = "terra is not a good party member"
os.environ["RIP_CHANGES_QUEUE_URL"] = "http://lol"

def _create_sns_msg_wrapper(msg, changetype, eventsource):
    inner_msg = {
        "Type" : "Notification",
        "Message" : msg,
        "MessageAttributes" : {
                "dimensionType" : {"Type":"String","Value":"REGION"},
                "newEntry" : {"Type":"String","Value":"false"},
                "changeType" : {"Type":"String","Value":changetype},
                "changeStatus" : {"Type":"String","Value":"APPROVED"},
                "registrant" : {"Type":"String","Value":"region-build-automation"},
                "lifeCycle" : {"Type":"String","Value":"NotAnUpdate"},
                "dimensionName" : {"Type":"String","Value":"BPM"}
        }
    }
    return {
        'receiptHandle': 'AQEBX2mJ...blahblahblah',
        'body': json.dumps(inner_msg, separators=(',', ':')),   # removes unnecessary whitespace
        'eventSource': eventsource
    }


def _create_message(filename, changetype=None, eventsource='aws:sqs'):
    script_dir = os.path.dirname(__file__) # regardless of the current directory, script_dir is the folder holding this test_ingest_rip_changes.py file
    full_filename = os.path.join(script_dir, '..', 'test_messages', filename)
    with open(full_filename, 'r') as input_file:
        content_str = input_file.read()
        content_squished = json.dumps(json.loads(content_str), separators=(',', ':'))  # strips unnecessary whitespace
        return _create_sns_msg_wrapper(content_squished, changetype, eventsource)


def _test_region_message():
    return _create_message('region.json', 'DimensionChange')


def _test_region_non_ga_message():
    return _create_message('region_non_ga.json')


def _test_retail_region():
    return _create_message('retail_region_change.json', 'DimensionChange')


def _test_region_titan_message():
    return _create_message('titan.json')


def _test_feature_change():
    return _create_message('feature_change.json', 'FeatureInstanceChange')


def _test_unknown_dimension_message():
    return _create_message('unknown_dimension.json')


def _test_approved_service_message():
    return _create_message('approved_service.json', 'ServiceStatusChange')


def _test_pending_service_message():
    return _create_message('pending_service.json', 'DimensionChange')


def _test_pending_service_message_not_from_sqs():
    return _create_message('not_from_sqs.json', 'DimensionChange', eventsource='aws:lambda')


def _test_serviceinstance_message():
    return _create_message('service_instance.json', 'ServiceStatusChange')


def _test_new_component_service_message():
    return _create_message('new_component_service.json', 'NewComponentService')


def _test_new_service_message():
    return _create_message('new_service.json', 'NewService')


def _test_serviceinstances_goes_ga_message():
    return _create_message('service_instance_goes_ga.json', 'ServiceStatusChange')


def _test_serviceinstance_in_cell_message():
    return _create_message('service_instance_in_cell.json')


@pytest.fixture
def rip_ingestor():
    ingestor = RipChangesIngestor(
        event={ 'Records': [ _test_pending_service_message(), _test_region_message() ] },
        metrics_service_name="foo",
    )
    return ingestor

@pytest.fixture
def rip_ingestor_integtation():
    ingestor = RipChangesIngestor(
        event={ 'Records': [ _test_pending_service_message_not_from_sqs() ] },
        metrics_service_name="foo",
    )
    return ingestor


@pytest.mark.parametrize("inputstr, expectedout", [
    ('', False),
    ('asdfasd', False),
    ('recon-integ', True),
    ('recon-integ-2', False),
    ('test-recon-integ', False),
    ('rms-integ', False),
    ('rms-integ-service', True),
    ('rms-integ-service+booyah', True),
    ('rms-canary-service', True),
    ('rms-canary-service+test', True)
])
def test_is_in_list_of_ignored_services(inputstr, expectedout):
    assert is_in_list_of_ignored_services(inputstr) == expectedout


@pytest.fixture
def fields_in_imported_rip_region(status_value):
    return {"status": status_value, "airport_code": "IAD"}


def validate_region_item_from_fields(fields):
    mock_region_item = Mock()
    mock_region_item.local_item = fields
    return validate_region_item(mock_region_item)


@pytest.mark.parametrize('status_value', ["GA"])
def test_validate_region_item(fields_in_imported_rip_region):
    assert validate_region_item_from_fields(fields_in_imported_rip_region) is not None


@pytest.mark.parametrize('status_value', ["GA"])
def test_validate_region_item_without_status(fields_in_imported_rip_region):
    fields_in_imported_rip_region.pop("status")
    assert validate_region_item_from_fields(fields_in_imported_rip_region) is None


@pytest.mark.parametrize('status_value', [""])
def test_validate_region_item_empty_status(fields_in_imported_rip_region):
    assert validate_region_item_from_fields(fields_in_imported_rip_region) is None


@pytest.mark.parametrize('status_value', ["THIS IS AN ILLEGAL STATUS"])
def test_validate_region_item_with_invalid_status(fields_in_imported_rip_region):
    assert validate_region_item_from_fields(fields_in_imported_rip_region) is None


@unittest.mock.patch('regions_recon_lambda.ingest_rip_changes.RipChangesIngestor', autospec=True)
def test_lambda_entry_point(mocked_class):
    fake_lambda_context = unittest.mock.Mock()
    fake_lambda_context.function_name = "here we go again"
    event = { "Records": [ _test_pending_service_message(), _test_serviceinstance_message() ] }
    ingest_rip_changes(
        event=event,
        context=fake_lambda_context,
    )
    mocked_class.assert_called_with(metrics_service_name=fake_lambda_context.function_name, event=event)


def test_get_sqs_client(rip_ingestor):
    with unittest.mock.patch('boto3.client', autospec=True) as mocked_boto_client:
        assert mocked_boto_client.called is False
        rip_ingestor.get_sqs_client()
        assert mocked_boto_client.called is True


def test_delete_sqs_message(rip_ingestor):
    mocked_client = unittest.mock.Mock()
    rip_ingestor.get_sqs_client = unittest.mock.Mock(return_value=mocked_client)
    dummy_handle = "foo bar!"
    rip_ingestor.delete_sqs_message(handle=dummy_handle)
    assert rip_ingestor.get_sqs_client.called is True
    mocked_client.delete_message.assert_called_with(QueueUrl=os.environ["RIP_CHANGES_QUEUE_URL"], ReceiptHandle=dummy_handle)


@unittest.mock.patch('regions_recon_lambda.ingest_rip_changes.submit_cloudwatch_metrics', autospec=True)
def test_run_workflow_with_writes(mocked_submit_cloudwatch_metrics, rip_ingestor):
    rip_ingestor.write_to_dynamo = unittest.mock.Mock()
    rip_ingestor.process_rip_message = unittest.mock.Mock()
    rip_ingestor.delete_sqs_message = unittest.mock.Mock()
    rip_ingestor.run_workflow()
    assert rip_ingestor.write_to_dynamo.called is True
    assert mocked_submit_cloudwatch_metrics.called is True
    for record in rip_ingestor.records:
        rip_ingestor.delete_sqs_message.assert_any_call(handle=record.receipt_handle)
        rip_ingestor.process_rip_message.assert_any_call(message=record.message)


@unittest.mock.patch('regions_recon_lambda.ingest_rip_changes.submit_cloudwatch_metrics', autospec=True)
def test_run_workflow_with_writes_no_sqs_message(mocked_submit_cloudwatch_metrics, rip_ingestor_integtation):
    rip_ingestor_integtation.write_to_dynamo = unittest.mock.Mock()
    rip_ingestor_integtation.process_rip_message = unittest.mock.Mock()
    rip_ingestor_integtation.delete_sqs_message = unittest.mock.Mock()
    for record in rip_ingestor_integtation.records:
        record.receipt_handle = None
    rip_ingestor_integtation.run_workflow()
    assert rip_ingestor_integtation.write_to_dynamo.called is True
    assert mocked_submit_cloudwatch_metrics.called is True
    for record in rip_ingestor_integtation.records:
        rip_ingestor_integtation.delete_sqs_message.assert_not_called()
        rip_ingestor_integtation.process_rip_message.assert_any_call(message=record.message)


@unittest.mock.patch('regions_recon_lambda.ingest_rip_changes.submit_cloudwatch_metrics', autospec=True)
def test_run_workflow_without_writes(mocked_submit_cloudwatch_metrics, rip_ingestor):
    rip_ingestor.write_to_dynamo = unittest.mock.Mock()
    rip_ingestor.process_rip_message = unittest.mock.Mock()
    rip_ingestor.delete_sqs_message = unittest.mock.Mock()
    rip_ingestor.records = [ RipMessageRecord(_test_feature_change()) ]  # override the data our fixture provided
    rip_ingestor.run_workflow()
    assert rip_ingestor.write_to_dynamo.called is False
    assert mocked_submit_cloudwatch_metrics.called is True
    assert rip_ingestor.metrics["ignored_change_type"] > 0
    for record in rip_ingestor.records:
        rip_ingestor.delete_sqs_message.assert_any_call(handle=record.receipt_handle)
        rip_ingestor.process_rip_message.called is False


@unittest.mock.patch('regions_recon_lambda.ingest_rip_changes.submit_cloudwatch_metrics', autospec=True)
def test_run_workflow_titan(mocked_submit_cloudwatch_metrics, rip_ingestor):
    rip_ingestor.write_to_dynamo = unittest.mock.Mock()
    rip_ingestor.process_rip_message = unittest.mock.Mock()
    rip_ingestor.delete_sqs_message = unittest.mock.Mock()
    rip_ingestor.records = [ RipMessageRecord(_test_region_titan_message()) ]  # override the data our fixture provided
    rip_ingestor.run_workflow()
    assert rip_ingestor.write_to_dynamo.called is False
    assert mocked_submit_cloudwatch_metrics.called is True
    assert 'unknown_dimension_type' not in rip_ingestor.metrics


def test_write_to_dynamo(rip_ingestor):
    mock_table = unittest.mock.Mock()
    mock_batch_opener = unittest.mock.Mock()
    mock_batch_writer = unittest.mock.Mock()
    mock_batch_opener.__enter__ = unittest.mock.Mock(return_value=mock_batch_writer)
    mock_batch_opener.__exit__ = unittest.mock.Mock(return_value=None)
    mock_table.batch_writer.return_value = mock_batch_opener
    rip_ingestor.get_table = unittest.mock.Mock(return_value=mock_table)
    rip_ingestor.ddb_items_to_write = [{"a": "small bug"}, {"b": "big bug"}, {"c": "biggest bug"}]
    rip_ingestor.write_to_dynamo()
    for item in rip_ingestor.ddb_items_to_write:
        mock_batch_writer.put_item.assert_any_call(Item=item)


@pytest.mark.parametrize("sample_record,expected_metrics,is_processable", [
    (_test_approved_service_message(), {}, True),  # "service_change" metric incremented in a different function
    (_test_serviceinstance_message(), {}, True),  # "service_change" metric incremented in a different function
    (_test_serviceinstance_in_cell_message(), {}, True),  # "unsupported_parent_dimension" defined in a different function
    (_test_region_message(), {}, True),  # "region_change" metric incremented in a different function
    (_test_pending_service_message(), {"change_not_approved": 1}, False),
    (_test_unknown_dimension_message(), {"unknown_dimension_type": 1}, False),
    ])
def test_process_rip_message_happy_paths(sample_record, expected_metrics, is_processable, rip_ingestor):
    mocked_buildable = unittest.mock.Mock()
    mocked_buildable.items_pending_write = []
    mocked_buildable.local_item = {"artifact": "TEST", "instance": "test:v0", "status": "GA", "airport_code": "IAD"}
    mocked_buildable.metrics = {}
    rip_ingestor.get_buildable_service = unittest.mock.Mock(return_value=mocked_buildable)
    rip_ingestor.get_buildable_region = unittest.mock.Mock(return_value=mocked_buildable)
    body = json.loads(sample_record["body"])
    message = json.loads(body["Message"])
    with unittest.mock.patch.object(BuildablesItem, "create_and_backfill", Mock):
        rip_ingestor.process_rip_message(message=message)
    for expected_metric, expected_value in expected_metrics.items():
        assert rip_ingestor.metrics[expected_metric] == expected_value
    assert mocked_buildable.backfill_item_with_ddb_data.called is is_processable


@unittest.mock.patch('regions_recon_lambda.ingest_rip_changes.validate_region_item', autospec=True)
def test_process_rip_message_no_matching_buildable_region(mocked_validate_region_item, rip_ingestor):
    test_message = {
        "status": "APPROVED",
        "dimension": {
            "type": "REGION"
        }
    }
    rip_ingestor.get_buildable_region = unittest.mock.Mock(return_value=None)
    rip_ingestor.process_rip_message(test_message)
    mocked_validate_region_item.assert_not_called()


def assert_common_buildable_operations(rip_ingestor, record):
    body = json.loads(record["body"])
    message = json.loads(body["Message"])
    buildable_service = rip_ingestor.get_buildable_service(message=message)
    assert rip_ingestor.metrics["service_change"] == 1
    assert isinstance(buildable_service, BuildableService)
    rip_ingestor.get_service_metadata.assert_called_with("rms-canary-service")


def test_get_buildable_service_New_service(rip_ingestor):
    rip_ingestor.get_table = unittest.mock.Mock()

    for record in [_test_new_service_message()]:
        body = json.loads(record["body"])
        message = json.loads(body["Message"])
        buildable_service = rip_ingestor.get_buildable_service(message=message)
        assert rip_ingestor.metrics["service_change"] == 1
        assert isinstance(buildable_service, BuildableService)


@unittest.mock.patch('regions_recon_lambda.ingest_rip_changes.parent_object_exists', autospec=True)
def test_get_buildable_service_Component_Service_no_parent(mock_parent_object_exists, rip_ingestor):
    mock_parent_object_exists.return_value = False
    rip_ingestor.get_table = unittest.mock.Mock()

    for record in [_test_new_component_service_message()]:
        body = json.loads(record["body"])
        message = json.loads(body["Message"])
        buildable_service = rip_ingestor.get_buildable_service(message=message)
        assert buildable_service is None


@unittest.mock.patch('regions_recon_lambda.ingest_rip_changes.parent_object_exists', autospec=True)
def test_get_buildable_service_Component_Service_with_parent(mock_parent_object_exists, rip_ingestor):
    mock_parent_object_exists.return_value = True
    rip_ingestor.get_table = unittest.mock.Mock()

    for record in [_test_new_component_service_message()]:
        body = json.loads(record["body"])
        message = json.loads(body["Message"])
        buildable_service = rip_ingestor.get_buildable_service(message=message)
        assert rip_ingestor.metrics["service_change"] == 1
        assert isinstance(buildable_service, BuildableService)


@unittest.mock.patch('regions_recon_lambda.ingest_rip_changes.parent_object_exists', autospec=True)
def test_get_buildable_service(mock_parent_object_exists, rip_ingestor):
    mock_parent_object_exists.return_value = True
    rip_ingestor.get_table = unittest.mock.Mock()
    rip_ingestor.get_service_metadata = unittest.mock.Mock(return_value={"instance": "rms-canary-service:v0", "plan": "Globally Expanding - Mandatory"})

    for record in [_test_serviceinstance_message()]:
        assert_common_buildable_operations(rip_ingestor, record)
        assert rip_ingestor.metrics["pulled_plan_from_parent"] == 1


@unittest.mock.patch('regions_recon_lambda.ingest_rip_changes.parent_object_exists', autospec=True)
def test_get_buildable_service_no_parent(mock_parent_object_exists, rip_ingestor):
    mock_parent_object_exists.return_value = False
    rip_ingestor.get_table = unittest.mock.Mock()

    for record in [_test_serviceinstance_message()]:
        body = json.loads(record["body"])
        message = json.loads(body["Message"])
        buildable_service = rip_ingestor.get_buildable_service(message=message)
        assert buildable_service is None


@unittest.mock.patch('regions_recon_lambda.ingest_rip_changes.parent_object_exists', autospec=True)
def test_get_buildable_service_saves_ga_launch_date(mock_parent_object_exists, rip_ingestor):
    mock_parent_object_exists.return_value = True
    rip_ingestor.get_table = unittest.mock.Mock()
    rip_ingestor.get_service_metadata = unittest.mock.Mock(return_value={"instance": "rms-canary-service:v0", "plan": "Globally Expanding - Mandatory"})
    for record in [_test_serviceinstances_goes_ga_message()]:
        assert_common_buildable_operations(rip_ingestor, record)
        assert rip_ingestor.metrics["save_ga_launched_date"] == 1


@unittest.mock.patch('regions_recon_lambda.ingest_rip_changes.parent_object_exists', autospec=True)
def test_get_buildable_service_removes_confidence_when_ga(mock_parent_object_exists, rip_ingestor):
    mock_parent_object_exists.return_value = True
    rip_ingestor.get_table = unittest.mock.Mock()
    rip_ingestor.get_service_metadata = unittest.mock.Mock(return_value={"instance": "rms-canary-service:v0", "plan": "Globally Expanding - Mandatory"})
    for record in [_test_serviceinstances_goes_ga_message()]:
        assert_common_buildable_operations(rip_ingestor, record)
        assert rip_ingestor.metrics["remove_ga_confidence"] == 1


@unittest.mock.patch('regions_recon_lambda.ingest_rip_changes.parent_object_exists', autospec=True)
def test_get_buildable_service_without_MD_Object(mock_parent_object_exists, rip_ingestor):
    mock_parent_object_exists.return_value = True
    rip_ingestor.get_table = unittest.mock.Mock()
    rip_ingestor.get_service_metadata = unittest.mock.Mock(return_value=None)
    for record in [_test_serviceinstance_message()]:
        assert_common_buildable_operations(rip_ingestor, record)
        assert rip_ingestor.metrics.get("pulled_plan_from_parent") == None


@unittest.mock.patch('regions_recon_lambda.ingest_rip_changes.parent_object_exists', autospec=True)
def test_get_buildable_service_with_MD_Object_without_plan(mock_parent_object_exists, rip_ingestor):
    mock_parent_object_exists.return_value = True
    rip_ingestor.get_table = unittest.mock.Mock()
    rip_ingestor.get_service_metadata = unittest.mock.Mock(return_value={"instance": "rms-canary-service:v0"})
    for record in [_test_serviceinstance_message()]:
        assert_common_buildable_operations(rip_ingestor, record)
        assert rip_ingestor.metrics.get("pulled_plan_from_parent") == None


@unittest.mock.patch('regions_recon_lambda.ingest_rip_changes.execute_retryable_call', autospec=True)
def test_get_service_metadata(mocked_execute_retryable_call, rip_ingestor):
    rip_ingestor.get_table = unittest.mock.Mock()
    mocked_execute_retryable_call.return_value = { "Item": {"instance": "rms-canary-service:v0"}}
    result = rip_ingestor.get_service_metadata("rms-canary-service")
    assert mocked_execute_retryable_call.called is True
    assert result == {"instance": "rms-canary-service:v0"}


@unittest.mock.patch('regions_recon_lambda.ingest_rip_changes.execute_retryable_call', autospec=True)
def test_get_service_metadata_not_found(mocked_execute_retryable_call, rip_ingestor):
    rip_ingestor.get_table = unittest.mock.Mock()
    mocked_execute_retryable_call.return_value = None
    result = rip_ingestor.get_service_metadata("rms-canary-service")
    assert mocked_execute_retryable_call.called is True
    assert result == None


def test_get_buildable_region(rip_ingestor):
    rip_ingestor.get_table = unittest.mock.Mock()
    for record in [_test_region_message(), _test_region_non_ga_message()]:
        rip_ingestor.metrics["region_change"] = 0
        body = json.loads(record["body"])
        message = json.loads(body["Message"])
        buildable_region = rip_ingestor.get_buildable_region(message=message)
        assert rip_ingestor.metrics["region_change"] == 1
        assert isinstance(buildable_region, BuildableRegion)


def test_get_buildable_region_no_statusdate(rip_ingestor):
    rip_ingestor.get_table = unittest.mock.Mock()
    for record in [_test_region_non_ga_message()]:
        body = json.loads(record["body"])
        message = json.loads(body["Message"])
        del(message["newValue"]["statusDates"])
        buildable_region = rip_ingestor.get_buildable_region(message=message)
        assert isinstance(buildable_region, BuildableRegion)


def test_get_buildable_region_has_tags(rip_ingestor):
    rip_ingestor.get_table = unittest.mock.Mock()
    for record in [_test_region_non_ga_message()]:
        rip_ingestor.metrics["region_change"] = 0
        body = json.loads(record["body"])
        message = json.loads(body["Message"])
        buildable_region = rip_ingestor.get_buildable_region(message=message)
        assert buildable_region.local_item["tags"] != "tags"
        assert isinstance(buildable_region, BuildableRegion)


def test_retail_region_noop(rip_ingestor):
    rip_ingestor.get_table = unittest.mock.Mock()
    for record in [_test_retail_region()]:
        rip_ingestor.metrics["region_change"] = 0
        body = json.loads(record["body"])
        message = json.loads(body["Message"])
        buildable_region = rip_ingestor.get_buildable_region(message=message)
        assert buildable_region is None


@unittest.mock.patch('regions_recon_lambda.ingest_rip_changes.parent_object_exists', autospec=True)
def test_get_buildable_service_cell(mock_parent_object_exists, rip_ingestor):
    """Test a special case of the above.  In this case, the parent dimension's type is one we don't handle."""
    mock_parent_object_exists.return_value = True
    rip_ingestor.get_table = unittest.mock.Mock()
    record = _test_serviceinstance_in_cell_message()
    body = json.loads(record["body"])
    message = json.loads(body["Message"])
    buildable_service = rip_ingestor.get_buildable_service(message=message)
    assert rip_ingestor.metrics["unsupported_parent_dimension"] == 1
    assert buildable_service is None


def test_get_attributes_from_new_value(rip_ingestor):
    sample_buildables_attr_name = "this is the buildables item attr name"
    sample_buildables_attr_value = "got this one"
    attribute_map = {
        "foobarA": sample_buildables_attr_name,
        "foobarB": "blah2",
    }
    sample_new_value = {
        "foobarA": sample_buildables_attr_value,
        "other key": "but not this one",
    }
    cherrypicked_attrs = rip_ingestor.get_attributes_from_new_value(map_of_attr_names=attribute_map, new_value=sample_new_value)
    expected = {
        sample_buildables_attr_name: sample_buildables_attr_value,
    }
    assert cherrypicked_attrs == expected


def test_get_date_iso_string_from_epoch_milliseconds_timestamp(rip_ingestor):
    dt = rip_ingestor.get_date_iso_string_from_epoch_milliseconds_timestamp(timestamp=1564454017014)
    assert isinstance(dt, str)
