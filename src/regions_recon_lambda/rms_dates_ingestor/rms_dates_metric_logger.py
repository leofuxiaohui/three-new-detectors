from regions_recon_python_common.utils.cloudwatch_metrics_utils import submit_cloudwatch_metrics

FUNCTION_NAME = "RMSDatesScheduledJobFunction"


def __log_metric(metric_name: str, count: int):
    submit_cloudwatch_metrics({metric_name: count}, FUNCTION_NAME)


def metric_log_rms_response_does_not_contain_dates_key(count: int = 1):
    __log_metric("rms_response_invalid", count)


def metric_log_rms_response_does_not_have_ga_milestone(count: int = 1):
    __log_metric("no_ga_milestone_found", count)


def metric_log_no_change_in_rms_projected_ga_date(count: int = 1):
    __log_metric("ddb_item_already_uptodate", count)


def metric_log_change_in_rms_projected_ga_date(count: int = 1):
    __log_metric("ddb_updated_item", count)
