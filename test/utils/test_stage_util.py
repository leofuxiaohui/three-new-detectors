from unittest.mock import patch

from regions_recon_lambda.utils.stage_util import is_prod_stage, STAGE_KEY, PROD_STAGE, is_gamma_or_prod_stage


@patch("regions_recon_lambda.utils.stage_util.os")
def test_is_prod_stage(mock_os):
    mock_os.environ = {STAGE_KEY: 'beta'}
    assert not is_prod_stage()

    mock_os.environ = {STAGE_KEY: PROD_STAGE}
    assert is_prod_stage()


@patch("regions_recon_lambda.utils.stage_util.os")
def test_is_gamma_or_prod_stage(mock_os):
    mock_os.environ = {STAGE_KEY: 'beta'}
    assert not is_gamma_or_prod_stage()

    mock_os.environ = {STAGE_KEY: PROD_STAGE}
    assert is_prod_stage()
