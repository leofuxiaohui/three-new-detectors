from typing import TypeVar, Type

from regions_recon_python_common.buildable_item import BuildableRegion, BuildableItem, BuildableService
from regions_recon_python_common.buildables_dao_models.buildables_item import INSTANCE_DELIMITER, BuildablesItem
from regions_recon_python_common.buildables_dao_models.buildables_versioned_item import BuildablesVersionedItem
from regions_recon_python_common.buildables_dao_models.region_metadata import RegionMetadata
from regions_recon_python_common.buildables_dao_models.service_metadata import ServiceMetadata
from regions_recon_python_common.buildables_dao_models.service_plan import ServicePlan


SERVICE_METADATA_DELIMITER_COUNT = 1
SERVICE_PLAN_DELIMITER_COUNT = 2


T = TypeVar('T', bound=BuildablesItem)
V = TypeVar('V', bound=BuildablesVersionedItem)

UPDATING_ATTRIBUTES = frozenset(("updated", "updater", "updating_agent"))


def _convert_buildable_item_to_model(buildable_item: BuildableItem, model_type: Type[T]) -> T:
    return model_type.create_and_backfill(**{
        attribute: buildable_item.local_item[attribute]
        for attribute in model_type.get_attributes()
        if attribute in buildable_item.local_item
    })


def _convert_buildable_item_to_versioned_model(buildable_item: BuildableItem, model_type: Type[BuildablesVersionedItem]) -> V:
    buildable_item_attributes = buildable_item.local_item
    model = model_type.create_and_backfill(**{
        attribute: buildable_item.local_item[attribute]
        for attribute in model_type.get_attributes()
        if attribute in buildable_item_attributes and attribute not in UPDATING_ATTRIBUTES
    })

    if not model.updater:
        for updating_attribute in UPDATING_ATTRIBUTES:
            setattr(model, updating_attribute, buildable_item_attributes.get(updating_attribute))

    else:
        model.set_updater_on_version_increment(buildable_item_attributes.get("updater"), buildable_item_attributes.get("updating_agent"))

    return model


def convert_buildable_region_to_model(buildable_region: BuildableRegion) -> RegionMetadata:
    return _convert_buildable_item_to_model(buildable_region, RegionMetadata)


def convert_buildable_service_metadata_to_model(buildable_service: BuildableService) -> ServiceMetadata:
    return _convert_buildable_item_to_versioned_model(buildable_service, ServiceMetadata)


def convert_buildable_service_plan_to_model(buildable_service: BuildableService) -> ServicePlan:
    return _convert_buildable_item_to_versioned_model(buildable_service, ServicePlan)


def is_service(buildable_item: BuildableItem):
    return buildable_item.local_item.get("artifact", "") == "SERVICE"


def is_service_metadata(buildable_item: BuildableItem):
    return is_service(buildable_item) and buildable_item.local_item.get("instance", "").count(INSTANCE_DELIMITER) == SERVICE_METADATA_DELIMITER_COUNT


def is_service_plan(buildable_item: BuildableItem):
    return is_service(buildable_item) and buildable_item.local_item.get("instance", "").count(INSTANCE_DELIMITER) == SERVICE_PLAN_DELIMITER_COUNT
