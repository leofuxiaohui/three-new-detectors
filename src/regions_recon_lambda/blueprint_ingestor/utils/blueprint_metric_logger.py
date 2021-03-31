import os
from collections import defaultdict

from regions_recon_python_common.utils.cloudwatch_metrics_utils import submit_cloudwatch_metrics

VALID_KEY = os.environ.get("VALID_ITEMS_METRIC_LABEL")
API_VIOLATION_KEY = os.environ.get("API_VIOLATION_METRIC_LABEL")
INVALID_KEY = os.environ.get("INVALID_ITEMS_METRIC_LABEL")
IGNORED_KEY = os.environ.get("IGNORED_ITEMS_METRIC_LABEL")

__blueprint_metrics = defaultdict(int)


def increment_valid_blueprint_items():
    __blueprint_metrics[VALID_KEY] += 1


def increment_api_violation_blueprint_items():
    __blueprint_metrics[API_VIOLATION_KEY] += 1


def increment_invalid_blueprint_items():
    __blueprint_metrics[INVALID_KEY] += 1


def increment_ignored_blueprint_items():
    __blueprint_metrics[IGNORED_KEY] += 1


def submit_blueprint_metrics(service_name: str):
    submit_cloudwatch_metrics(__blueprint_metrics, service_name)
    __blueprint_metrics.clear()
