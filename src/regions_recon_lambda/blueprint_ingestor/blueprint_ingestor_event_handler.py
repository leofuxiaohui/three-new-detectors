from regions_recon_python_common.buildables_dao_models.blueprint_high_water_mark import BlueprintHighWaterMark
from regions_recon_python_common.utils.log import get_logger

from regions_recon_lambda.blueprint_ingestor.dao.blueprint_dao import BlueprintDAO
from regions_recon_lambda.blueprint_ingestor.record_processors.blueprint_record_processor import \
    handle_all_data_items
from regions_recon_lambda.blueprint_ingestor.utils.blueprint_metric_logger import submit_blueprint_metrics
from regions_recon_lambda.blueprint_ingestor.utils.high_water_mark_utils import get_high_water_mark_or_default
from regions_recon_lambda.blueprint_ingestor.utils.security_utils import get_honeycode_client_from_event
from regions_recon_lambda.blueprint_ingestor.utils.update_invalid_records import clear_no_longer_invalid_records

logger = get_logger()


def ingest_blueprint(event, context):
    honeycode_client = get_honeycode_client_from_event(event)

    if not honeycode_client:
        return "Failure: Could not assume role"

    next_high_water_mark = BlueprintHighWaterMark.create_from_current_time()
    blueprint_iterator = BlueprintDAO(honeycode_client).get_iterator(get_high_water_mark_or_default())
    plans_to_update = handle_all_data_items(blueprint_iterator)
    clear_no_longer_invalid_records(plans_to_update.get_encountered_uids())
    next_high_water_mark.save()
    logger.info(f"Wrote the next high-water mark of {next_high_water_mark.to_blueprint_format()}")
    submit_blueprint_metrics(context.function_name)
    return "Success! Ingested Blueprint data"
