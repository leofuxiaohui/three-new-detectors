from typing import List, Dict, Optional, Iterator, FrozenSet

from regions_recon_python_common.buildables_dao_models.blueprint_invalid_record import BlueprintInvalidRecord
from regions_recon_python_common.buildables_dao_models.blueprint_record import BlueprintRecord as BuildablesBlueprintRecord

from regions_recon_python_common.data_models.plan import Plan
from regions_recon_python_common.utils.log import get_logger

from regions_recon_lambda.blueprint_ingestor.data_records.plans_update import PlansToUpdate
from regions_recon_lambda.blueprint_ingestor.data_records.blueprint_record import BlueprintRecord
from regions_recon_lambda.blueprint_ingestor.exceptions import InvalidBlueprintDataException
from regions_recon_lambda.blueprint_ingestor.utils.blueprint_metric_logger import \
    increment_api_violation_blueprint_items, increment_ignored_blueprint_items, increment_invalid_blueprint_items, \
    increment_valid_blueprint_items
from regions_recon_lambda.blueprint_ingestor.utils.handle_blueprint_plan_change import change_blueprint_plans
from regions_recon_lambda.blueprint_ingestor.utils.plan_update_utils import determine_plans_to_remove

logger = get_logger()


EXPECTED_NUMBER_OF_FORMATTED_VALUE_FIELDS = 9


def convert_data_items_to_blueprint_record(data_items: List[Dict[str, str]]) -> BlueprintRecord:
    logger.info(f"Processing the following data item from blueprint {data_items}")
    formatted_value_items = [
        item["formattedValue"]
        for item in data_items
        if "formattedValue" in item
    ]

    if len(formatted_value_items) != EXPECTED_NUMBER_OF_FORMATTED_VALUE_FIELDS:
        raise InvalidBlueprintDataException(f"Expected {EXPECTED_NUMBER_OF_FORMATTED_VALUE_FIELDS} "
                                            f"\"formattedValue\"s in the dataItems list from Blueprint")

    return BlueprintRecord(*formatted_value_items)


def handle_blueprint_data_item(data_item: List[Dict[str, str]]) -> Optional[BlueprintRecord]:
    blueprint_record: BlueprintRecord

    try:
        blueprint_record = convert_data_items_to_blueprint_record(data_item)

    except InvalidBlueprintDataException:
        logger.warning(f"[API Violation] {data_item}")
        increment_api_violation_blueprint_items()
        return None

    if blueprint_record.should_ignore():
        logger.info(f"[IGNORED BLUEPRINT DATA ITEM] {data_item}")
        increment_ignored_blueprint_items()
        return None

    validation_errors = blueprint_record.get_validation_errors()

    if validation_errors:
        logger.warning(f"[INVALID BLUEPRINT DATA ITEM] Found the following validation problems {validation_errors} "
                       f"in the Blueprint record {data_item}")
        invalid_blueprint_record = BlueprintInvalidRecord.create(blueprint_record.uid)
        set_all_invalid_blueprint_record_fields(invalid_blueprint_record, blueprint_record)
        invalid_blueprint_record.validation_errors = validation_errors
        invalid_blueprint_record.save()
        increment_invalid_blueprint_items()
        return None

    logger.info(f"Received the following valid data item from blueprint {data_item}")
    increment_valid_blueprint_items()
    return blueprint_record


def handle_blueprint_record(blueprint_record: BlueprintRecord,
                            plans_to_update: PlansToUpdate) -> BuildablesBlueprintRecord:
    buildables_blueprint_record = BuildablesBlueprintRecord.get_if_present(blueprint_record.uid)
    plans_to_add: FrozenSet[Plan] = Plan.generate_plans(blueprint_record.service_rip_short_name,
                                                        blueprint_record.get_airport_codes())

    if not buildables_blueprint_record:
        logger.info(f"Could not find a matching blueprint record in buildables for {blueprint_record} from blueprint")
        buildables_blueprint_record = BuildablesBlueprintRecord.create(blueprint_record.uid)
        set_all_blueprint_record_fields(buildables_blueprint_record, blueprint_record)
        buildables_blueprint_record.save()
        plans_to_update.update_or_add_uid_to_plans(blueprint_record.uid, plans_to_add)
        logger.info(f"Created {buildables_blueprint_record} in buildables")
        return buildables_blueprint_record

    logger.info(f"The matching blueprint record in buildables is {buildables_blueprint_record} for {blueprint_record}")
    set_blueprint_record_fields_except_service_and_regions(buildables_blueprint_record, blueprint_record)
    buildables_blueprint_record.save()
    logger.info(f"Updated all regions exception for service and region for {buildables_blueprint_record}")

    plan_change_args = dict(
        old_service=buildables_blueprint_record.service_rip_short_name,
        old_regions=frozenset(buildables_blueprint_record.regions),
        new_service=blueprint_record.service_rip_short_name,
        new_regions=frozenset(blueprint_record.get_airport_codes())
    )

    plans_to_update.update_or_add_uid_to_plans(blueprint_record.uid, plans_to_add)
    plans_to_update.remove_uid_from_plans(blueprint_record.uid, determine_plans_to_remove(**plan_change_args))

    return buildables_blueprint_record


def set_blueprint_record_fields_except_service_and_regions(buildables_blueprint_record: BuildablesBlueprintRecord,
                                                           blueprint_record: BlueprintRecord):
    buildables_blueprint_record.est_launch_date = blueprint_record.est_launch_date_to_datetime()
    buildables_blueprint_record.last_updated_date = blueprint_record.last_updated_date_to_datetime()
    buildables_blueprint_record.updater_email = blueprint_record.updater_email
    buildables_blueprint_record.confidence = blueprint_record.confidence
    buildables_blueprint_record.state = blueprint_record.state
    buildables_blueprint_record.note = blueprint_record.note
    buildables_blueprint_record.instance = blueprint_record.uid


def set_service_and_regions(buildables_blueprint_record: BuildablesBlueprintRecord,
                            blueprint_record: BlueprintRecord):
    buildables_blueprint_record.service_rip_short_name = blueprint_record.service_rip_short_name
    buildables_blueprint_record.regions = blueprint_record.get_airport_codes()


def set_all_blueprint_record_fields(buildables_blueprint_record: BuildablesBlueprintRecord,
                                    blueprint_record: BlueprintRecord):
    set_blueprint_record_fields_except_service_and_regions(buildables_blueprint_record, blueprint_record)
    set_service_and_regions(buildables_blueprint_record, blueprint_record)


def set_all_invalid_blueprint_record_fields(buildables_invalid_blueprint_record: BlueprintInvalidRecord,
                                            blueprint_record: BlueprintRecord):
    buildables_invalid_blueprint_record.instance = blueprint_record.uid
    buildables_invalid_blueprint_record.service_rip_short_name = blueprint_record.service_rip_short_name
    buildables_invalid_blueprint_record.est_launch_date = blueprint_record.est_launch_date
    buildables_invalid_blueprint_record.last_updated_date = blueprint_record.last_updated_date
    buildables_invalid_blueprint_record.updater_email = blueprint_record.updater_email
    buildables_invalid_blueprint_record.confidence = blueprint_record.confidence
    buildables_invalid_blueprint_record.state = blueprint_record.state
    buildables_invalid_blueprint_record.note = blueprint_record.note
    buildables_invalid_blueprint_record.regions = blueprint_record.regions


def get_valid_blueprint_records(blueprint_data_item_iterator: Iterator) -> Iterator[BlueprintRecord]:
    return filter(None, [
        handle_blueprint_data_item(data_item)
        for data_item in blueprint_data_item_iterator
    ])


def handle_all_data_items(blueprint_data_item_iterator: Iterator) -> PlansToUpdate:
    plans_to_update = PlansToUpdate()

    matching_records = [
        (blueprint_record, handle_blueprint_record(blueprint_record, plans_to_update))
        for blueprint_record in get_valid_blueprint_records(blueprint_data_item_iterator)
    ]

    change_blueprint_plans(plans_to_update)

    for (blueprint_record, buildables_blueprint_record) in matching_records:
        set_service_and_regions(buildables_blueprint_record, blueprint_record)
        buildables_blueprint_record.save()
        logger.info(f"Updated the service and region of {buildables_blueprint_record}")

    return plans_to_update
