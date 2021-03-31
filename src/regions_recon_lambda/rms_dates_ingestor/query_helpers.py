from typing import Iterator, List

from regions_recon_python_common.buildables_dao_models.service_metadata import SERVICE_METADATA_LATEST_ARTIFACT, \
    ServiceMetadataLatest
from regions_recon_python_common.buildables_dao_models.service_plan import PLAN_BY_SERVICE_ARTIFACT, \
    PlanByService
from regions_recon_python_common.query_utils.region_metadata_query_utils import get_region_metadata
from regions_recon_python_common.utils.log import get_logger
from regions_recon_python_common.utils.rms_managed_regions import get_regions_within_one_day_post_launch, \
    get_regions_within_ninety_business_days_post_launch

logger = get_logger()

LAUNCH_BLOCKING_SERVICE_PLAN = "Globally Expanding - Launch Blocking"
MANDATORY_SERVICE_PLAN = "Globally Expanding - Mandatory"


def get_launch_blocking_services() -> Iterator[ServiceMetadataLatest]:
    return ServiceMetadataLatest.artifact_plan_index.query(
        SERVICE_METADATA_LATEST_ARTIFACT,
        range_key_condition=ServiceMetadataLatest.plan == LAUNCH_BLOCKING_SERVICE_PLAN
    )


def get_mandatory_services() -> Iterator[ServiceMetadataLatest]:
    return ServiceMetadataLatest.artifact_plan_index.query(
        SERVICE_METADATA_LATEST_ARTIFACT,
        range_key_condition=ServiceMetadataLatest.plan == MANDATORY_SERVICE_PLAN
    )


def get_rms_managed_plans() -> List[PlanByService]:
    region_metadata = get_region_metadata()

    rms_managed_launch_blocking_service_regions = [
        (service, region)
        for region in get_regions_within_one_day_post_launch(region_metadata)
        for service in get_launch_blocking_services()
    ]

    rms_managed_mandatory_service_regions = [
        (service, region)
        for region in get_regions_within_ninety_business_days_post_launch(region_metadata)
        for service in get_mandatory_services()
    ]

    rms_managed_plan_keys = rms_managed_launch_blocking_service_regions + rms_managed_mandatory_service_regions

    logger.debug(f"Performing batch get on a total of {len(rms_managed_plan_keys)} potential keys "
                 f"which are calculated from the product of categorized services and rms managed regions")

    rms_managed_plans = list(PlanByService.batch_get([
        (PLAN_BY_SERVICE_ARTIFACT, f"{service.instance}:{region.airport_code}")
        for service, region in rms_managed_plan_keys
    ]))

    logger.debug(f"Received {len(rms_managed_plans)} from buildables")
    
    return rms_managed_plans
