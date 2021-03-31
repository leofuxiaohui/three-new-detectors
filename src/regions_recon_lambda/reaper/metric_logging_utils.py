import json
import os

from regions_recon_python_common.utils.log import get_logger

logger = get_logger()


def log_delete_items_metric(function_name: str, number_of_deleted_items: int):
    logger.info(json.dumps({
        "log_type": "METRIC",
        "service_name": function_name,
        "metric_name": os.environ.get("DELETED_ITEMS_METRIC_LABEL"),
        "metric_value": number_of_deleted_items
    }))
