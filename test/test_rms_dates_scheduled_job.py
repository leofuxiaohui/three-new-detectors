import unittest
from unittest.mock import patch

import pytest

from regions_recon_lambda.rms_dates_scheduled_job import get_GE_service_dates_from_buildables_for_region
from regions_recon_lambda.rms_dates_scheduled_job import (get_rms_and_recon_combined_object,
                                                          call_rms_and_create_diff_object,
                                                          find_service_and_update_dynamo)
from regions_recon_lambda.rms_dates_scheduled_job import pull_and_write_rms_dates, get_status_from_rip_arn


def test_get_GE_service_dates_from_buildables_for_region_happy():
    # build mocks
    expected_item = {
        "instance": "snowballedge:v0:MXP",
        "artifact": "SERVICE", "airport_code": "MXP", "region": "MXP",
        "belongs_to_artifact": "REGION", "belongs_to_instance": "MXP",
        "plan": "Globally Expanding - Mandatory",
        "changed_attributes": [ "date", "note"],
        "confidence": "Green", "date": "2020-08-26", "status": "BUILD",
        "note": "Ops and Dev resourcing to complete end-to-end fulfillment. ",
        "rms_early_finish_date": "2020-05-13",
        "rms_early_finish_date_updated": "2020-05-05T15:09:24.161832",
        "updater": "rkm",
        "updated": "2020-04-09T17:17:55.454004",
        "updating_agent": "DynamoDbBuildablesDb by sbx_user1051 on 2020-04-09 17:17",
        "version_instance": 0,
        "version_latest": 12
    }

    mock_query_ret_val = {
        "Items": [expected_item]
    }
    mock_table = unittest.mock.Mock()
    mock_table.query = unittest.mock.Mock(return_value=mock_query_ret_val)

    fake_region = "MXP"

    # call function
    response = get_GE_service_dates_from_buildables_for_region(mock_table, fake_region)
    # check results
    # TODO: sdeshong - checks if function concats correctly, but this test needs improvements
    assert response == [expected_item, expected_item]


def test_get_rms_and_recon_combined_object_happy_no_date():
    with unittest.mock.patch('regions_recon_lambda.rms_dates_scheduled_job.validate_rms_milestone', autospec=True) as validate_milestone:
        fake_milestones = [{
            "early_finish": "2020-04-15T06:59:00.000000+0000",
            "early_start": "2020-04-15T06:59:00.000000+0000",
            "late": 0,
            "late_finish": "2020-04-21T06:59:00.000000+0000",
            "late_start": "2020-04-21T06:59:00.000000+0000",
            "milestone_name": "s3-GA",
            "milestone_type": "RIP_SERVICE",
            "namespace": "arn:aws:rip:::instance/service/s3/MXP/GA",
            "region": "mxp",
            "service": "s3",
            "slack": 4,
            "status": "NOT_STARTED"
        }]
        fake_service = { "instance": "s3:v0:MXP" }

        expected_result = {
            "service": "s3",
            "region": "MXP",
            "service_launch_date": "-",
            "rms_early_finish_date": "2020-04-14",
            "slack": 4,
            "date_diff": None
        }

        result = get_rms_and_recon_combined_object(fake_milestones, fake_service)
        assert result == expected_result
        validate_milestone.assert_called_once


def test_get_rms_and_recon_combined_object_happy_with_date():
    fake_milestones = [{
        "early_finish": "2020-04-15T06:59:00.000000+0000",
        "early_start": "2020-04-15T06:59:00.000000+0000",
        "late": 0,
        "late_finish": "2020-04-21T06:59:00.000000+0000",
        "late_start": "2020-04-21T06:59:00.000000+0000",
        "milestone_name": "s3-GA",
        "milestone_type": "RIP_SERVICE",
        "namespace": "arn:aws:rip:::instance/service/s3/MXP/GA",
        "region": "mxp",
        "service": "s3",
        "slack": 4,
        "status": "NOT_STARTED"
    }]
    fake_service = {
        "instance": "s3:v0:MXP",
        "date": "2020-04-16"
    }

    expected_result = {
        "service": "s3",
        "region": "MXP",
        "service_launch_date": "2020-04-15",
        "rms_early_finish_date": "2020-04-14",
        "slack": 4,
        "date_diff": -1
    }

    result = get_rms_and_recon_combined_object(fake_milestones, fake_service)
    assert result == expected_result


def test_get_rms_and_recon_combined_object_happy_with_completed_milestone():
    fake_milestones = [{
        "early_finish": "2020-04-15T06:59:00.000000+0000",
        "early_start": "2020-04-15T06:59:00.000000+0000",
        "late": 0,
        "late_finish": "2020-04-21T06:59:00.000000+0000",
        "late_start": "2020-04-21T06:59:00.000000+0000",
        "milestone_name": "s3-GA",
        "milestone_type": "RIP_SERVICE",
        "namespace": "arn:aws:rip:::instance/service/s3/MXP/GA",
        "region": "mxp",
        "service": "s3",
        "slack": 4,
        "status": "COMPLETED"
    }]
    fake_service = {
        "instance": "s3:v0:MXP",
        "date": "2020-04-16"
    }

    expected_result = {
        "service": "s3",
        "region": "MXP",
        "service_launch_date": "2020-04-15",
        "rms_early_finish_date": "COMPLETED",
        "slack": None,
        "date_diff": None
    }

    result = get_rms_and_recon_combined_object(fake_milestones, fake_service)
    assert result == expected_result


def test_call_rms_and_create_diff_object_happy():
    with unittest.mock.patch('requests.get', autospec=True) as mocked_requests_get:
        with unittest.mock.patch('regions_recon_lambda.rms_dates_scheduled_job.get_rms_and_recon_combined_object', autospec=True) as mock_get_combined_object:
            with unittest.mock.patch('simplejson.loads', autospec=True) as mock_json:
                fake_all_milestones = [ { "a": "b" } ]
                mocked_table = unittest.mock.Mock()
                mocked_table.content = unittest.mock.Mock()
                mocked_table.content.return_value = { "dates": fake_all_milestones }

                mock_json.return_value = { "dates": fake_all_milestones }

                mocked_requests_get.return_value = mocked_table
                mock_get_combined_object.return_value = []

                fake_auth = ""
                fake_service = { "instance": "s3:v0:MXP" }

                result = call_rms_and_create_diff_object(fake_auth, fake_service)

                assert result == []
                mock_get_combined_object.assert_called_with(fake_all_milestones, fake_service)


def test_find_service_and_update_dynamo_not_found():
    fake_data = {
        "service": "s3",
        "region": "MXP"
    }
    fake_all_services_plans = []

    assert not find_service_and_update_dynamo(fake_data, fake_all_services_plans)


def test_find_service_and_update_dynamo_found_but_no_write():
    fake_data = {
        "service": "s3",
        "region": "MXP",
        "rms_early_finish_date": "2020-04-20"
    }
    fake_all_services_plans = [{
        "instance": "s3:v0:MXP",
        "rms_early_finish_date": "2020-04-20"
    }]

    assert find_service_and_update_dynamo(fake_data, fake_all_services_plans)


@pytest.mark.parametrize("arn,expected_status", [
    ("arn:aws:rip:::instance/service/s3/MXP/GA", "GA"),
    ("arn:aws:rip:::instance/feature/s3/MXP/somefeature/BUILD", "BUILD"),
    ])
def test_get_status_from_rip_arn(arn, expected_status):
    result = get_status_from_rip_arn(arn)
    
    assert result == expected_status


@patch("regions_recon_lambda.rms_dates_scheduled_job.ServicePlan._get_if_present")
def test_find_service_and_update_dynamo_found_and_write(mocked_get_if_present):
    with unittest.mock.patch('simplejson.dumps', autospec=True) as json_dumps:
        fake_data = {
            "service": "s3",
            "region": "MXP",
            "rms_early_finish_date": "2020-04-20"
        }
        fake_all_services_plans = [{
            "instance": "s3:v0:MXP"
        }]
        json_dumps.return_value = "tangent likes icecream"

        mocked_service_plan_instance = unittest.mock.Mock()
        mocked_get_if_present.return_value = mocked_service_plan_instance

        assert find_service_and_update_dynamo(fake_data, fake_all_services_plans)
        assert mocked_service_plan_instance.rms_early_finish_date == "2020-04-20"


def test_pull_and_write_rms_dates():
    with unittest.mock.patch('boto3.resource', autospec=True) as mock_boto3_resource:
        with unittest.mock.patch('regions_recon_lambda.rms_dates_scheduled_job.get_GE_service_dates_from_buildables_for_region', autospec=True) as get_service_dates:
            with unittest.mock.patch('boto3.Session', autospec=True) as mock_session:
                with unittest.mock.patch('regions_recon_lambda.rms_dates_scheduled_job.call_rms_and_create_diff_object', autospec=True) as call_rms:
                    with unittest.mock.patch('regions_recon_lambda.rms_dates_scheduled_job.find_service_and_update_dynamo', autospec=True) as find_and_update:
                        with unittest.mock.patch("regions_recon_lambda.rms_dates_scheduled_job.submit_cloudwatch_metrics", autospec=True) as mocked_submit_cloudwatch_metrics:

                            # mock input things
                            fake_event = ""
                            fake_context = unittest.mock.Mock()

                            # mock table things
                            mock_ddb_resource = unittest.mock.Mock()
                            mock_ddb_resource.Table = unittest.mock.Mock()
                            mock_ddb_resource.Table.return_value = "Welcome to Recon Ethan"

                            get_service_dates.return_value = {"key": "test fail"}

                            # call the method
                            pull_and_write_rms_dates(fake_event, fake_context)

                            # check to see it did its 3 things
                            assert get_service_dates.call_count == 14
                            assert call_rms.call_count == 14
                            assert find_and_update.call_count == 14