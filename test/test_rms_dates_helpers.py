import unittest
from regions_recon_lambda.utils.rms_dates_helpers import days_between, valid_date, validate_service_name, validate_airport_code
from regions_recon_lambda.utils.rms_dates_helpers import validate_rms_milestone, get_short_date


def test_validate_rms_milestone_good():
    mock_logger = unittest.mock.Mock()
    mock_logger.error = unittest.mock.Mock()

    fake_milestone1 = {
        "namespace": "arn:aws:rip:::instance/service/mxp/s3/BUILD/Pre-Auth Build Start",
        "milestone_type": "RIP_SERVICE",
        "region": "mxp",
        "service": "s3",
        "status": "COMPLETED",
        "early_finish": "2019-10-21T07:00:00.000000+0000"
    }

    assert validate_rms_milestone(fake_milestone1, mock_logger) == True


def test_validate_rms_milestone_bad():
    mock_logger = unittest.mock.Mock()
    mock_logger.error = unittest.mock.Mock()
    fake_milestone = {}
    assert validate_rms_milestone(fake_milestone, mock_logger) == False


# date tests

def test_get_short_date_no_date():
    short_date = get_short_date("-")
    assert short_date == "-"

def test_get_short_date_no_time_no_timezone():
    short_date = get_short_date("2020-04-16")
    assert short_date == "2020-04-15"


def test_get_short_date_no_time_no_timezone_short_year():
    short_date = get_short_date("20-04-16")
    assert short_date == "2020-04-15"


def test_get_short_date_w_time_w_timezone_colon():
    short_date = get_short_date("2020-04-16T06:59:00.000000+00:00")
    assert short_date == "2020-04-15"


def test_get_short_date_w_time_w_timezone_no_colon():
    short_date = get_short_date("2020-04-16T06:59:00.000000+0000")
    assert short_date == "2020-04-15"


def test_get_short_date_w_time_no_timezone():
    short_date = get_short_date("2020-04-16 06:59")
    assert short_date == "2020-04-15"
