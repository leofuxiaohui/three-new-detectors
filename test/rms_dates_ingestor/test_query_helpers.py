from unittest.mock import patch

from freezegun import freeze_time
from regions_recon_python_common.buildables_dao_models.region_metadata import RegionMetadata
from regions_recon_python_common.buildables_dao_models.service_metadata import ServiceMetadataLatest
from regions_recon_python_common.buildables_dao_models.service_plan import PLAN_BY_SERVICE_ARTIFACT

from regions_recon_lambda.rms_dates_ingestor.query_helpers import get_rms_managed_plans


@freeze_time("2020-04-05 03:04:05", tz_offset=0)
@patch("regions_recon_lambda.rms_dates_ingestor.query_helpers.PlanByService")
@patch("regions_recon_lambda.rms_dates_ingestor.query_helpers.get_mandatory_services")
@patch("regions_recon_lambda.rms_dates_ingestor.query_helpers.get_launch_blocking_services")
@patch("regions_recon_lambda.rms_dates_ingestor.query_helpers.get_region_metadata")
def test_get_rms_managed_plans(mock_get_region_metadata,
                               mock_get_launch_blocking_services,
                               mock_get_mandatory_services,
                               mock_service_plan):
    mock_get_region_metadata.return_value = [
        RegionMetadata(date="2019-04-01", airport_code="TET"),
        RegionMetadata(date="2020-04-01", airport_code="TST"),
        RegionMetadata(date="2020-05-01", airport_code="TXT"),
    ]

    mock_get_launch_blocking_services.return_value = [ServiceMetadataLatest(instance="launchblocking")]
    mock_get_mandatory_services.return_value = [ServiceMetadataLatest(instance="mandatory")]

    get_rms_managed_plans()

    assert set(mock_service_plan.batch_get.call_args[0][0]) == {
        (PLAN_BY_SERVICE_ARTIFACT, instance)
        for instance in ("launchblocking:TXT", "mandatory:TST", "mandatory:TXT")
    }
