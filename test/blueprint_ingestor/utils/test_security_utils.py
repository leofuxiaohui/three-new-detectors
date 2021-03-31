import os
from unittest.mock import patch

from botocore.exceptions import ClientError

from regions_recon_lambda.blueprint_ingestor.utils.security_utils import get_honeycode_client_from_event


@patch.dict(os.environ, {"BLUEPRINT_ARN": "TEST"})
@patch("regions_recon_lambda.blueprint_ingestor.utils.security_utils.get_honeycode_client", autospec=True)
def test_cannot_assume_role(mock_get_honeycode_client):
    assert get_honeycode_client_from_event({})

    mock_get_honeycode_client.return_value = "Success"
    assert get_honeycode_client_from_event({"arn": "CAN ASSUME"})

    mock_get_honeycode_client.side_effect = ClientError({}, "TEST")
    assert not get_honeycode_client_from_event({"arn": "CANNOT ASSUME"})
