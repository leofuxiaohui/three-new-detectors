from dataclasses import replace

from regions_recon_lambda.blueprint_ingestor.data_records.blueprint_record import BlueprintRecord, \
    SERVICE_NAME_TO_IGNORE
from regions_recon_lambda.blueprint_ingestor.data_records.blueprint_record import CANCELLED_STATE

PROPER_BLUEPRINT_RECORD_ARGUMENTS = [
    "myservice",
    "10/5/24",
    "9/9/20 9:12",
    "venkyd@amazon.com",
    "Green",
    "In-Progress",
    "Venky's update",
    "26",
    "IAD - US East (N. Virginia); CMH - US East (Ohio); PDX - US West (Oregon); NRT - Asia Pacific (Tokyo)"
]

BLUEPRINT_RECORD = BlueprintRecord(*PROPER_BLUEPRINT_RECORD_ARGUMENTS)


def test_should_ignore():
    ignore_blueprint_record = replace(BLUEPRINT_RECORD, service_rip_short_name=SERVICE_NAME_TO_IGNORE)
    assert ignore_blueprint_record.should_ignore()


def test_should_ignore_cancelled_no_last_updated():
    ignore_blueprint_record = replace(BLUEPRINT_RECORD, state=CANCELLED_STATE, last_updated_date="")
    assert ignore_blueprint_record.should_ignore()


def test_should_ignore_valid_record():
    assert not BLUEPRINT_RECORD.should_ignore()


def test_validation_errors_valid_record():
    assert not BLUEPRINT_RECORD.get_validation_errors()


def test_validation_errors_invalid_last_updated():
    invalid_last_updated = replace(BLUEPRINT_RECORD, last_updated_date="9/9/20 9:12 PM")
    assert invalid_last_updated.get_validation_errors()


def test_validation_errors_empty_service_name():
    empty_service_name = replace(BLUEPRINT_RECORD, service_rip_short_name="")
    assert empty_service_name.get_validation_errors()


def test_validation_errors_invalid_note():
    test_note = replace(BLUEPRINT_RECORD, note="test")
    assert test_note.get_validation_errors()


def test_validation_errors_invalid_regions():
    invalid_regions = replace(BLUEPRINT_RECORD, regions="THISISNOTANAIRPORTCODE")
    assert invalid_regions.get_validation_errors()


def test_get_airport_codes():
    assert BLUEPRINT_RECORD.get_airport_codes() == frozenset(("IAD", "CMH", "PDX", "NRT"))


def test_est_launch_date_to_datetime():
    assert BLUEPRINT_RECORD.est_launch_date_to_datetime()


def test_last_update_date_to_datetime():
    assert BLUEPRINT_RECORD.last_updated_date_to_datetime()
