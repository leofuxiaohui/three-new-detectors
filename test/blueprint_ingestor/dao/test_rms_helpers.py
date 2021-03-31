import unittest
import pytest
from unittest import mock
from test_rip_helpers import MockRIPHelperLocal, MockServiceMetadata
from mock_logger import MockLogger
from regions_recon_python_common.utils.log import get_logger
from regions_recon_lambda.utils import rip_helpers as rip
from regions_recon_lambda.utils import rms_helpers as rms
from rip_helper_local import RIPHelperLocal

@pytest.fixture
def mock_cpt_data():
    return [
        {
            "arn":"arn:aws:rmsv2:::test/000",
            "status":"NOT_STARTED",
            "dimension":"COMMERCIAL_PARTITION_TEMPLATE",
            "service":"ecytu"
        },
        {
            "arn":"arn:aws:rmsv2:::test/001",
            "status":"NOT_STARTED",
            "dimension":"COMMERCIAL_PARTITION_TEMPLATE",
            "service":"sword"
        },
        {
            "arn":"arn:aws:rmsv2:::test/002",
            "status":"STARTED",
            "dimension":"COMMERCIAL_PARTITION_TEMPLATE",
            "service":"stree"
        },
        {
            "arn":"arn:aws:rmsv2:::test/003",
            "status":"NOT_STARTED",
            "dimension":"COMMERCIAL_PARTITION_TEMPLATE",
            "service":"netsky"
        },
        {
            "arn":"arn:aws:rmsv2:::test/004",
            "status":"NOT_STARTED",
            "dimension":"COMMERCIAL_PARTITION_TEMPLATE",
            "service":"stree"            
        }
    ]

@unittest.mock.patch('regions_recon_lambda.utils.rms_helpers.get_logger')
@unittest.mock.patch('regions_recon_lambda.utils.rip_helpers.RIPHelperLocal', autospec=MockRIPHelperLocal)
def test_create_rms_service_dict_one_value(rip_helper, patched_mock_logger, mock_cpt_data):
    mock_rip_helper = MockRIPHelperLocal()
    rip_helper.return_value.service.side_effect = mock_rip_helper.service
    patched_mock_logger.return_value = MockLogger()
    service_dict = rms.create_rms_service_dict(mock_cpt_data, ["arn"])

    expected_result = {
        "stree": {
            "arn": ["arn:aws:rmsv2:::test/002", "arn:aws:rmsv2:::test/004"]
        },
        "ecytu": {
            "arn": ["arn:aws:rmsv2:::test/000"]
        }
    }
    assert service_dict == expected_result

@unittest.mock.patch('regions_recon_lambda.utils.rms_helpers.get_logger')
@unittest.mock.patch('regions_recon_lambda.utils.rip_helpers.RIPHelperLocal', autospec=MockRIPHelperLocal)
def test_create_rms_service_dict_multi_value(rip_helper, patched_mock_logger, mock_cpt_data):
    mock_rip_helper = MockRIPHelperLocal()
    rip_helper.return_value.service.side_effect = mock_rip_helper.service
    patched_mock_logger.return_value = MockLogger()
    service_dict = rms.create_rms_service_dict(mock_cpt_data, ["arn", "status"])

    expected_result = {
        "stree": {
            "arn": ["arn:aws:rmsv2:::test/002", "arn:aws:rmsv2:::test/004"],
            "status": ["STARTED", "NOT_STARTED"]
        },
        "ecytu": {
            "arn": ["arn:aws:rmsv2:::test/000"],
            "status": ["NOT_STARTED"]
        }
    }
    assert service_dict == expected_result

@mock.patch("regions_recon_lambda.utils.api_helpers.retry_get_requests", autospec=True)
@mock.patch("regions_recon_lambda.utils.rms_helpers.get_rms_response", autospec=True)
def test_get_rms_data(get_rms_response, mock_retry_get_requests):
    fake_json = {
        "spacerocks": [
            {
                "arn": "moo",
                "namespace": "$default",
                "resourceId": "someuniquething",
                "name": "Boring",
                "status": "NOT_STARTED",
                "dimension": "MEL",
                "service": "killallhumans",
                "latestChangeArn": "someotheruniquething",
            }
        ],
        "nextToken": None,
    }
    mock_retry_get_requests.return_value.json.return_value = fake_json
    get_rms_response.return_value = (fake_json, None)
    mock_endpoint = "spacerocks"
    mock_host = "mock_host"
    mock_rmsauth = mock.Mock()
    mock_dimension = "MockDimension"
    expected_data = [
        {
            "arn": "moo",
            "namespace": "$default",
            "resourceId": "someuniquething",
            "name": "Boring",
            "status": "NOT_STARTED",
            "dimension": "MEL",
            "service": "killallhumans",
            "latestChangeArn": "someotheruniquething",
        }
    ]
    data = rms.get_rms_data(aws_host=mock_host, auth=mock_rmsauth, endpoint=mock_endpoint, dimension=mock_dimension)
    assert data == expected_data