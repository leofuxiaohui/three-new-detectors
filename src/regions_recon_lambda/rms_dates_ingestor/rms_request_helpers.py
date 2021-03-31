import json
import urllib.parse
from typing import Iterable, Dict, Optional

import requests
from aws_requests_auth.aws_auth import AWSRequestsAuth
from regions_recon_python_common.utils.log import get_logger

from regions_recon_lambda.rms_dates_ingestor.rms_dates_metric_logger import metric_log_rms_response_does_not_contain_dates_key, \
    metric_log_rms_response_does_not_have_ga_milestone
from regions_recon_lambda.utils.constants import AWS_RMS_ANALYTICS
from regions_recon_lambda.utils.rms_dates_helpers import get_short_date

logger = get_logger()


def get_rms_date_milestones(service: str, region: str, rms_request_auth: AWSRequestsAuth) -> Iterable[Dict[str, str]]:
    encoded_service = urllib.parse.quote(service.replace("/", "+"))
    encoded_region = urllib.parse.quote(region)

    rms_api_endpoint = f"https://{AWS_RMS_ANALYTICS}/dates?region={encoded_region}&service={encoded_service}"
    logger.debug(f"Making API request to RMS: {rms_api_endpoint}")
    rms_dates_api_response = requests.get(rms_api_endpoint, auth=rms_request_auth)
    logger.debug(f"Received API response from RMS")

    rms_dates_api_response_dict = json.loads(rms_dates_api_response.content)
    rms_dates_milestones = rms_dates_api_response_dict.get("dates")

    if rms_dates_milestones is None:
        metric_log_rms_response_does_not_contain_dates_key()
        logger.warning(f"Could not get RMS date milestone information for {service} in {region}. Full response: {rms_dates_api_response_dict}")
        return []

    return rms_dates_milestones


def get_rms_projected_ga_date_from_milestones(service: str, region: str, rms_date_milestones: Iterable[Dict[str, str]]) -> Optional[str]:
    matching_ga_milestone = f"instance/service/{service}/{region}/GA"

    for milestone in rms_date_milestones:
        if matching_ga_milestone in milestone.get("namespace", "") and milestone.get("early_finish"):
            return "COMPLETED" if milestone.get("status") == "COMPLETED" else get_short_date(milestone.get("early_finish"))

    logger.debug(f"Could not determine an RMS projected GA date for {service} in {region}")
    metric_log_rms_response_does_not_have_ga_milestone()
