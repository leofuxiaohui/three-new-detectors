from regions_recon_lambda.rms_dates_ingestor.auth_util import get_rms_request_auth
from regions_recon_lambda.rms_dates_ingestor.query_helpers import get_rms_managed_plans
from regions_recon_lambda.rms_dates_ingestor.rms_dates_updater import get_service_plans_with_update, \
    update_service_plans, log_updated_rms_projected_dates


def update_rms_projected_ga_dates(event, context):
    rms_managed_plans = get_rms_managed_plans()
    rms_request_auth = get_rms_request_auth()

    service_plans_with_update = get_service_plans_with_update(rms_managed_plans, rms_request_auth)
    update_service_plans(service_plans_with_update)
    log_updated_rms_projected_dates(rms_managed_plans, service_plans_with_update)
