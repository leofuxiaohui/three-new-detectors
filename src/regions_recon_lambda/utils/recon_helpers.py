import requests
import boto3
import urllib
from regions_recon_lambda.utils.constants import AWS_HOST_RECON, AWS_HOST_RECON_BETA, AWS_REGION_EAST, ServicePlan
from regions_recon_lambda.utils.api_helpers import retry_get_requests, url_token_checker, get_aws_auth
from aws_requests_auth.aws_auth import AWSRequestsAuth
from regions_recon_python_common.utils.log import get_logger

def find_plan(service: str):
    logger = get_logger()
    recon_auth = get_aws_auth(AWS_HOST_RECON, AWS_REGION_EAST)

    logger.info(f"Fetching the plan categorization for {service}...")
    data = get_recon_data(AWS_HOST_RECON, recon_auth, f"services/{service}/plans")
    logger.info(f"Data retrieved:\n{data}")
    plan = data.get("service", {}).get("plan")
    if plan == ServicePlan.LAUNCH_BLOCKING.value:
        return ServicePlan.LAUNCH_BLOCKING
    elif plan == ServicePlan.MANDATORY.value:
        return ServicePlan.MANDATORY
    else:
        return ServicePlan.NON_GLOBAL

def get_services_with_plan():
    logger = get_logger()
    recon_auth = get_aws_auth(AWS_HOST_RECON, AWS_REGION_EAST)

    logger.info(f"Fetching all services with a plan categorization...")
    data = get_recon_data(AWS_HOST_RECON, recon_auth, "services")
    logger.info(f"Data retrieved:\n{data}")
    return data

def get_recon_data(aws_host: str, auth: AWSRequestsAuth, endpoint: str, **kwargs):
    logger = get_logger()
    query_params = urllib.parse.urlencode(kwargs)
    url = urllib.parse.urlunparse(("https", aws_host, f"api/{endpoint}", None, query_params, None))
    logger.info(f'Making recon request with:\n{url}')
    json_object = get_recon_response(auth, url)
    logger.info(f'Response received:\n{json_object}')
    return json_object

def get_recon_response(recon_auth: AWSRequestsAuth, url: str):
    logger = get_logger()
    json_object = {}
    try: 
        response = retry_get_requests(url, auth=recon_auth)
        response.raise_for_status()
        json_object = response.json()
        logger.info(f"Recon response received:\n{json_object}")
    except requests.exceptions.HTTPError as e: 
        logger.error(e)

    return json_object

def update_service_plan(service: str, plan: ServicePlan):
    logger = get_logger()
    plan_str = "" if plan == ServicePlan.UNCATEGORIZED else plan.value
    recon_auth = get_aws_auth(AWS_HOST_RECON_BETA, AWS_REGION_EAST)
    patch_params = {
         "op": "replace", "path": "/plan", "value": plan_str
    }
    url = urllib.parse.urlunparse(("https", AWS_HOST_RECON_BETA, f"api/services/{service}", None, None, None))
    logger.info(f"Sending patch request to update the plan of {service} with new value \"{plan_str}\"...")
    with requests.patch(url, data=patch_params, auth=recon_auth) as response:
        logger.info(f"Response received:\n{response}")
