from typing import Iterable, Type, Union

from regions_recon_python_common.buildables_dao_models.buildables_item import BuildablesItem
from regions_recon_python_common.buildables_dao_models.buildables_versioned_item import BuildablesVersionedItem
from regions_recon_python_common.buildables_dao_models.service_metadata import SERVICE_METADATA_VERSIONED_ARTIFACT, \
    ServiceMetadata
from regions_recon_python_common.buildables_dao_models.service_plan import ServicePlan, SERVICE_PLAN_VERSIONED_ARTIFACT
from regions_recon_python_common.utils.log import get_logger

RECON_INTEG_VERSION_DELETION_THRESHOLD = 15
RMS_CANARY_PREFIX = "rms-canary-service"
RECON_INTEG_PREFIX = "recon-integ"
RECON_INTEG_SERVICE_METADATA = ("recon-integ", "recon-integ-2")
SERVICE_TYPE = Union[ServicePlan, ServiceMetadata]

logger = get_logger()


def get_rms_canary_items() -> Iterable[BuildablesItem]:
    return BuildablesItem.query(
        SERVICE_METADATA_VERSIONED_ARTIFACT,
        range_key_condition=BuildablesItem.instance.startswith(RMS_CANARY_PREFIX)
    )


def write_and_reset_service_item(service_type: Type[SERVICE_TYPE], services_to_reset: Iterable[SERVICE_TYPE]):
    with service_type.batch_write() as batch:
        for service in services_to_reset:
            logger.info(f"Resetting version version_latest for {service} from {service.version_latest} to {RECON_INTEG_VERSION_DELETION_THRESHOLD}")
            service.version_latest = RECON_INTEG_VERSION_DELETION_THRESHOLD
            batch.save(service)


def reset_recon_service_metadata():
    recon_integ_metadata: Iterable[ServiceMetadata] = ServiceMetadata.batch_get([
        (SERVICE_METADATA_VERSIONED_ARTIFACT, f"{recon_integ_service}:v0")
        for recon_integ_service in RECON_INTEG_SERVICE_METADATA
    ])

    metadata_to_reset = [
        metadata
        for metadata in recon_integ_metadata
        if metadata.version_latest > RECON_INTEG_VERSION_DELETION_THRESHOLD
    ]

    write_and_reset_service_item(ServiceMetadata, metadata_to_reset)


def reset_recon_service_plans():
    plans_to_reset: Iterable[ServicePlan] = ServicePlan.query(
        SERVICE_PLAN_VERSIONED_ARTIFACT,
        range_key_condition=ServicePlan.instance.startswith(f"{RECON_INTEG_PREFIX}:v0:"),
        filter_condition=ServicePlan.version_latest > RECON_INTEG_VERSION_DELETION_THRESHOLD
    )

    write_and_reset_service_item(ServicePlan, plans_to_reset)


def reset_recon_integ_items():
    reset_recon_service_metadata()
    reset_recon_service_plans()


def get_recon_integ_items() -> Iterable[BuildablesItem]:
    return BuildablesVersionedItem.query(
        SERVICE_METADATA_VERSIONED_ARTIFACT,
        range_key_condition=BuildablesVersionedItem.instance.startswith(RECON_INTEG_PREFIX),
        filter_condition=BuildablesVersionedItem.version_instance > RECON_INTEG_VERSION_DELETION_THRESHOLD
    )
