from typing import Set, Iterable

from regions_recon_python_common.buildables_dao_models.blueprint_plan import BlueprintPlan
from regions_recon_python_common.data_models.plan import Plan
from regions_recon_python_common.utils.log import get_logger

from regions_recon_lambda.blueprint_ingestor.data_records.plans_update import PlansToUpdate

logger = get_logger()


def handle_buildables_blueprint_received_plans(buildables_blueprint_plans: Iterable[BlueprintPlan],
                                               plans_to_update: PlansToUpdate):
    for buildables_blueprint_plan in buildables_blueprint_plans:
        plan = Plan(buildables_blueprint_plan.get_service(), buildables_blueprint_plan.get_region())
        uids_to_add_or_update = plans_to_update.get_update_or_add_uids(plan)
        uids_to_remove = plans_to_update.get_uids_to_remove(plan)
        logger.info(f"Updating uids for {buildables_blueprint_plans}, adding or updating {uids_to_add_or_update} "
                    f"and removing {uids_to_remove}")
        buildables_blueprint_plan.add_uids(uids_to_add_or_update)
        buildables_blueprint_plan.remove_uids(uids_to_remove)
        logger.info(f"Recalculating the launch date for {buildables_blueprint_plan}")
        buildables_blueprint_plan.recalculate()


def convert_buildables_blueprint_plans_to_plans(
        buildables_blueprint_plans: Iterable[BlueprintPlan]) -> Set[Plan]:
    return {Plan(plan.get_service(), plan.get_region()) for plan in buildables_blueprint_plans}


def handle_unmatched_plans(unmatched_plans: Iterable[Plan], plans_to_update: PlansToUpdate):
    for plan in unmatched_plans:
        logger.info(f"Could not find a matching blueprint plan in buildables for {plan}, so we will create it")
        buildables_blueprint_plan = BlueprintPlan.create(plan.service, plan.region)
        uids_to_add = plans_to_update.get_update_or_add_uids(plan)
        logger.info(f"Adding the following uids {uids_to_add} to {buildables_blueprint_plan} ")
        buildables_blueprint_plan.add_uids(uids_to_add)
        logger.info(f"Recalculating the launch date for {buildables_blueprint_plan}")
        buildables_blueprint_plan.recalculate()


def change_blueprint_plans(plans_to_update: PlansToUpdate):
    plans = set(plans_to_update.keys())

    buildables_blueprint_plan_keys = [BlueprintPlan.get_key(service, region) for service, region in plans]
    buildables_blueprint_plans = list(BlueprintPlan.batch_get(buildables_blueprint_plan_keys))
    handle_buildables_blueprint_received_plans(buildables_blueprint_plans, plans_to_update)

    matched_plans: Set[Plan] = convert_buildables_blueprint_plans_to_plans(buildables_blueprint_plans)
    unmatched_plans = plans.difference(matched_plans)

    handle_unmatched_plans(unmatched_plans, plans_to_update)
