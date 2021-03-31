from unittest.mock import Mock, patch

import pytest

from regions_recon_lambda.blueprint_ingestor.data_records.blueprint_record import BlueprintRecord, \
    SERVICE_NAME_TO_IGNORE
from regions_recon_lambda.blueprint_ingestor.exceptions import InvalidBlueprintDataException
from regions_recon_lambda.blueprint_ingestor.record_processors.blueprint_record_processor import \
    handle_blueprint_data_item, convert_data_items_to_blueprint_record, handle_blueprint_record, \
    get_valid_blueprint_records, handle_all_data_items
from regions_recon_python_common.data_models.plan import Plan

TEST_DATA_LIST = [
    "myservice",
    "08/31/20",
    "9/1/20 2:15",
    "venkyd@amazon.com",
    "Green",
    "In-Progress",
    "Ship it",
    "10281",
    "IAD - US East (N. Virginia); CMH - US East (Ohio); PDX - US West (Oregon); NRT - Asia Pacific (Tokyo)"
]

TEST_DATA_ITEMS = [
    {"formattedValue": item}
    for item in TEST_DATA_LIST
]


def change_index_for_data_items(index: int, value: str):
    new_data_items = [*TEST_DATA_LIST]
    new_data_items[index] = value
    return [
        {"formattedValue": item}
        for item in new_data_items
    ]


illegal_data_items = [*TEST_DATA_ITEMS]
illegal_data_items.pop()
illegal_data_items.append({"notFormattedValue": "illegal"})

BLUEPRINT_RECORD = BlueprintRecord(*TEST_DATA_LIST)


def change_blueprint_record(index: int, value: str) -> BlueprintRecord:
    new_proper_blueprint_record_arguments = [*TEST_DATA_LIST]
    new_proper_blueprint_record_arguments[index] = value
    return BlueprintRecord(*new_proper_blueprint_record_arguments)


def test_convert_data_items_to_blueprint_record():
    assert convert_data_items_to_blueprint_record(TEST_DATA_ITEMS).service_rip_short_name == TEST_DATA_LIST[0]


def test_convert_data_items_to_blueprint_record_with_illegal_argument_length():
    with pytest.raises(InvalidBlueprintDataException):
        convert_data_items_to_blueprint_record(illegal_data_items)


def test_handle_valid_blueprint_data_item():
    assert handle_blueprint_data_item(TEST_DATA_ITEMS)


def test_handle_api_violation_blueprint_data_item():
    new_test_data_items = [*TEST_DATA_ITEMS]
    new_test_data_items.pop()
    assert not handle_blueprint_data_item(new_test_data_items)


def test_handle_should_ignore_blueprint_data_item():
    assert not handle_blueprint_data_item(change_index_for_data_items(0, SERVICE_NAME_TO_IGNORE))


@patch("regions_recon_lambda.blueprint_ingestor.record_processors.blueprint_record_processor.BlueprintInvalidRecord", autospec=True)
def test_handle_validation_errors_blueprint_data_item(mocked_invalid_blueprint_record):
    created_record = Mock()
    mocked_invalid_blueprint_record.create.return_value = created_record
    handle_blueprint_data_item(change_index_for_data_items(8, "NOTAREGION"))
    created_record.save.assert_called_once()


@patch("regions_recon_lambda.blueprint_ingestor.record_processors.blueprint_record_processor.BuildablesBlueprintRecord", autospec=True)
def test_handle_blueprint_record_without_match(mocked_buildables_blueprint_record):
    mocked_buildables_blueprint_record.get_if_present.return_value = None
    created_record = Mock()
    mocked_buildables_blueprint_record.create.return_value = created_record
    plans_to_update = Mock()

    handle_blueprint_record(BLUEPRINT_RECORD, plans_to_update)

    assert plans_to_update.update_or_add_uid_to_plans.call_args[0][0] == BLUEPRINT_RECORD.uid
    assert Plan("myservice", "NRT") in plans_to_update.update_or_add_uid_to_plans.call_args[0][1]
    created_record.save.assert_called_once()


@patch("regions_recon_lambda.blueprint_ingestor.record_processors.blueprint_record_processor.BuildablesBlueprintRecord", autospec=True)
def test_handle_blueprint_record_with_match(mocked_buildables_blueprint_record):
    mocked_matching_record = Mock()
    mocked_matching_record.service_rip_short_name = BLUEPRINT_RECORD.service_rip_short_name
    mocked_matching_record.regions = {"IAD", "CMH", "PDX", "SFO"}  # NRT added and SFO removed
    mocked_buildables_blueprint_record.get_if_present.return_value = mocked_matching_record
    plans_to_update = Mock()

    handle_blueprint_record(BLUEPRINT_RECORD, plans_to_update)

    assert plans_to_update.update_or_add_uid_to_plans.call_args[0][0] == BLUEPRINT_RECORD.uid
    assert Plan("myservice", "NRT") in plans_to_update.update_or_add_uid_to_plans.call_args[0][1]
    assert frozenset([Plan("myservice", "SFO")]) == plans_to_update.remove_uid_from_plans.call_args[0][1]
    mocked_matching_record.save.assert_called_once()


@patch("regions_recon_lambda.blueprint_ingestor.record_processors.blueprint_record_processor.handle_blueprint_data_item", autospec=True)
def test_get_valid_blueprint_records(mocked_handle_blueprint_record_data_item):
    mocked_handle_blueprint_record_data_item.side_effect = [Mock(), None, Mock(), Mock(), None]
    assert len(list(get_valid_blueprint_records([Mock(), None, Mock(), Mock(), None]))) == 3


def test_handle_all_data_items_empty_list():
    handle_all_data_items([])


@patch("regions_recon_lambda.blueprint_ingestor.record_processors.blueprint_record_processor.change_blueprint_plans", autospec=True)
@patch("regions_recon_lambda.blueprint_ingestor.record_processors.blueprint_record_processor.handle_blueprint_record", autospec=True)
@patch("regions_recon_lambda.blueprint_ingestor.record_processors.blueprint_record_processor.get_valid_blueprint_records", autospec=True)
def test_handle_all_data_items_one_item(mocked_get_valid_blueprint_records,
                                        mocked_handle_blueprint_record,
                                        mocked_change_blueprint_plans):
    service_name = "SUCCESS"
    mocked_blueprint_record = Mock()
    mocked_blueprint_record.service_rip_short_name = service_name
    mocked_get_valid_blueprint_records.return_value = [mocked_blueprint_record]

    mocked_buildables_blueprint_record = Mock()
    mocked_handle_blueprint_record.return_value = mocked_buildables_blueprint_record
    handle_all_data_items([mocked_blueprint_record])
    assert mocked_buildables_blueprint_record.service_rip_short_name == service_name


@patch("regions_recon_lambda.blueprint_ingestor.record_processors.blueprint_record_processor.change_blueprint_plans", autospec=True)
@patch("regions_recon_lambda.blueprint_ingestor.record_processors.blueprint_record_processor.handle_blueprint_record", autospec=True)
@patch("regions_recon_lambda.blueprint_ingestor.record_processors.blueprint_record_processor.get_valid_blueprint_records", autospec=True)
def test_handle_all_data_items_two_items(mocked_get_valid_blueprint_records,
                                        mocked_handle_blueprint_record,
                                        mocked_change_blueprint_plans):
    service_name = "SUCCESS"
    service_name_two = "SUCCESS PART 2"

    mocked_blueprint_record = Mock()
    mocked_blueprint_record.service_rip_short_name = service_name

    mocked_blueprint_record_two = Mock()
    mocked_blueprint_record_two.service_rip_short_name = service_name_two

    mocked_get_valid_blueprint_records.return_value = [mocked_blueprint_record, mocked_blueprint_record_two]

    mocked_buildables_blueprint_record = Mock()
    mocked_buildables_blueprint_record_two = Mock()

    mocked_handle_blueprint_record.side_effect = [mocked_buildables_blueprint_record, mocked_buildables_blueprint_record_two]
    handle_all_data_items([mocked_blueprint_record, mocked_buildables_blueprint_record_two])
    assert mocked_buildables_blueprint_record.service_rip_short_name == service_name
    assert mocked_buildables_blueprint_record_two.service_rip_short_name == service_name_two
