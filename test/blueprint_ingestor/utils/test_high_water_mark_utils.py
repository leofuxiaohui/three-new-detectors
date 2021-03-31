from unittest.mock import patch, Mock

from regions_recon_lambda.blueprint_ingestor.utils.high_water_mark_utils import get_high_water_mark_or_default, \
    TIMESTAMP_TO_GET_ALL_BLUEPRINT_RECORDS


@patch("regions_recon_lambda.blueprint_ingestor.utils.high_water_mark_utils.BlueprintHighWaterMark", autospec=True)
def test_get_high_water_mark_or_default_no_high_water_mark(mocked_blueprint_high_water_mark):
    mocked_blueprint_high_water_mark.get_if_present.return_value = None
    assert get_high_water_mark_or_default() == TIMESTAMP_TO_GET_ALL_BLUEPRINT_RECORDS


@patch("regions_recon_lambda.blueprint_ingestor.utils.high_water_mark_utils.BlueprintHighWaterMark", autospec=True)
def test_get_high_water_mark_or_default_with_high_water_mark(mocked_blueprint_high_water_mark):
    test_high_water_mark = "05/26/2020 05:21:05 PM"
    mocked_high_water_mark = Mock()
    mocked_high_water_mark.to_blueprint_format.return_value = test_high_water_mark
    mocked_blueprint_high_water_mark.get_if_present.return_value = mocked_high_water_mark
    assert get_high_water_mark_or_default() == test_high_water_mark
