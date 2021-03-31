from regions_recon_lambda.reaper.delete import delete_items
from regions_recon_lambda.reaper.get_items_to_delete import get_rms_canary_items, reset_recon_integ_items, \
    get_recon_integ_items
from regions_recon_lambda.reaper.metric_logging_utils import log_delete_items_metric
from regions_recon_lambda.utils.stage_util import is_prod_stage


def reap(event, context) -> int:
    total_deleted_items = 0
    total_deleted_items += delete_items(get_rms_canary_items())

    if not is_prod_stage():
        reset_recon_integ_items()
        total_deleted_items += delete_items(get_recon_integ_items())

    log_delete_items_metric(context.function_name, total_deleted_items)

    return total_deleted_items
