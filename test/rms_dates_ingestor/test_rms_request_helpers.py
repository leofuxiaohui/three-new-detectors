from unittest.mock import patch, Mock

import pytest

from regions_recon_lambda.rms_dates_ingestor.rms_request_helpers import get_rms_date_milestones, \
    get_rms_projected_ga_date_from_milestones
from regions_recon_lambda.utils.constants import AWS_RMS_ANALYTICS


@pytest.mark.parametrize("mock_response_content, expected_response", [
    ("{}", []),
    ('{"No date information": "none"}', []),
    ('{"dates": ["milestone_one"]}', ["milestone_one"]),
])
@patch("regions_recon_lambda.rms_dates_ingestor.rms_request_helpers.requests")
def test_get_rms_date_milestones(mock_requests, mock_response_content, expected_response):
    mock_response = Mock()
    mock_response.content = mock_response_content
    mock_requests.get.return_value = mock_response
    mock_rms_request_auth = Mock()
    assert get_rms_date_milestones("lambda/test", "IAD", mock_rms_request_auth) == expected_response
    mock_requests.get.assert_called_with(f"https://{AWS_RMS_ANALYTICS}/dates?region=IAD&service=lambda%2Btest", auth=mock_rms_request_auth)


@pytest.mark.parametrize("milestones, expected_response", [
    ([], None),
    ([{}], None),
    ([{"Not namespace": ""}], None),
    ([{"namespace": "instance/service/lambda/IAD/IA"}], None),
    ([{"namespace": "instance/service/lambda/IAD/GA", "status": "COMPLETED", "early_finish": "2020-12-12T23:11:11"}], "COMPLETED"),
    ([{"namespace": "instance/service/lambda/IAD/GA", "status": "NOT COMPLETED"}], None),
    ([{"namespace": "instance/service/lambda/IAD/GA", "status": "NOT COMPLETED", "early_finish": "2020-12-12T23:11:11"}], "2020-12-12"),
    ([{"namespace": "instance/service/lambda/IAD/IA"}, {"namespace": "instance/service/lambda/IAD/GA", "status": "COMPLETED", "early_finish": "2020-12-12T23:11:11"}], "COMPLETED"),
])
def test_get_rms_projected_ga_date_from_milestones(milestones, expected_response):
    assert get_rms_projected_ga_date_from_milestones("lambda", "IAD", milestones) == expected_response
