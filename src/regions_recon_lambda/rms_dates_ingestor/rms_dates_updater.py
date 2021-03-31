from datetime import datetime
from typing import Iterable, List, Optional

from aws_requests_auth.aws_auth import AWSRequestsAuth
from regions_recon_python_common.buildables_dao_models.service_plan import PlanByService
from regions_recon_python_common.utils.log import get_logger

from regions_recon_lambda.rms_dates_ingestor.rms_dates_metric_logger import \
    metric_log_no_change_in_rms_projected_ga_date, metric_log_change_in_rms_projected_ga_date
from regions_recon_lambda.rms_dates_ingestor.rms_request_helpers import get_rms_date_milestones, \
    get_rms_projected_ga_date_from_milestones
from regions_recon_lambda.rms_dates_ingestor.service_plan_update import ServicePlanUpdate

logger = get_logger()


def get_service_plans_with_update(service_plans: Iterable[PlanByService], rms_request_auth: AWSRequestsAuth) -> List[ServicePlanUpdate]:
    service_plans_with_update: List[ServicePlanUpdate] = []

    for service_plan in service_plans:
        service, region = service_plan.get_service_region()

        rms_date_milestones = get_rms_date_milestones(service, region, rms_request_auth)
        rms_projected_ga_date: Optional[str] = get_rms_projected_ga_date_from_milestones(service, region, rms_date_milestones)

        if rms_projected_ga_date and rms_projected_ga_date != service_plan.rms_early_finish_date:
            service_plans_with_update.append(ServicePlanUpdate(service_plan, rms_projected_ga_date))
            logger.debug(f"The rms date of {service_plan.rms_early_finish_date} will be updated to {rms_projected_ga_date} for {service_plan}")

        else:
            logger.debug(f"The rms date of {service_plan.rms_early_finish_date} has not changed for {service_plan}")

    return service_plans_with_update


def update_service_plans(service_plans_with_update: List[ServicePlanUpdate]):
    service_region_to_update = {
        service_plan.primary_key: rms_date_update
        for service_plan, rms_date_update in service_plans_with_update
    }

    rms_projected_date_updated_time = datetime.utcnow().isoformat()
    logger.debug(f"Updating {len(service_region_to_update)} plans with new RMS projected GA dates")

    with PlanByService.batch_write() as service_plan_writer:
        for service_plan in PlanByService.batch_get(service_region_to_update.keys()):
            service_plan.rms_early_finish_date = service_region_to_update[service_plan.primary_key]
            service_plan.rms_early_finish_date_updated = rms_projected_date_updated_time
            service_plan_writer.save(service_plan)
            logger.debug(f"Updated {service_plan}'s RMS projected GA date to {service_plan.rms_early_finish_date}")


def log_updated_rms_projected_dates(service_plans: List[PlanByService], service_plans_with_update: List[ServicePlanUpdate]):
    not_updated = len(service_plans) - len(service_plans_with_update)
    updated = len(service_plans_with_update)

    metric_log_no_change_in_rms_projected_ga_date(not_updated)
    metric_log_change_in_rms_projected_ga_date(updated)
