import boto3
import urllib
import requests
from typing import Iterable, Dict
from aws_requests_auth.aws_auth import AWSRequestsAuth
from regions_recon_lambda.utils.constants import AWS_HOST_RMSV2, RmsEndpoint, AWS_REGION_EAST
from regions_recon_python_common.utils.log import get_logger
from regions_recon_lambda.utils import rip_helpers as rip
from regions_recon_lambda.utils.api_helpers import retry_get_requests, url_token_checker, get_aws_auth

def get_all_edges():
    logger = get_logger()
    logger.info(f"Fetching all of the RMS edges...")
    rmsv2_auth = get_aws_auth(AWS_HOST_RMSV2, AWS_REGION_EAST)
    fetched_data = get_rms_data(AWS_HOST_RMSV2, rmsv2_auth, RmsEndpoint.EDGES.value)
    logger.info(f"Edges retrieved:\n{fetched_data}")
    return fetched_data

def get_milestones_tasks_successors(arn: str, option: RmsEndpoint):
    logger = get_logger()
    rmsv2_auth = get_aws_auth(AWS_HOST_RMSV2, AWS_REGION_EAST)
    fetched_data = None
    if option == RmsEndpoint.MILESTONES or option == RmsEndpoint.TASKS:
        endpoints = [option.value]
    elif option == RmsEndpoint.MT:
        endpoints = [RmsEndpoint.MILESTONES.value, RmsEndpoint.TASKS.value]
    else:
        raise ValueError(f"{option} is not a supported option")

    fetched_data = [
        get_rms_data(AWS_HOST_RMSV2, rmsv2_auth, endpoint, predecessor=arn) for endpoint in endpoints
    ]
    logger.info(f"Grabbed the {option.value} succesors for ARN: {arn}:\n{fetched_data}")
    return fetched_data

"""
    Creates a dictionary from the json of the RMSV2 milestones/tasks endpoints where the first level keys are the services and
    the other keys of the json object are values.

    Ex. for given (data):
        [{
            "arn":"arn:aws:rmsv2:::test/000",
            "status":"NOT_STARTED",
            "dimension":"COMMERCIAL_PARTITION_TEMPLATE",
            "service":"ecytu"
        }]
    
    and (values):
        ["arn", dimension]

    returns:
        {
            ecytu: {
                arn: ["arn:aws:rmsv2:::test/000"],
                dimension: ["COMMERCIAL_PARTITION_TEMPLATE"]
            }
        }
"""
def create_rms_service_dict(data: Iterable[Dict[str, str]], values: Iterable[str]) -> Dict[str, Dict[str, Iterable[str]]]:
    logger = get_logger()
    return_dict = {}
    logger.debug(f"Creating services dictionary from \n{data}\nwith values {values}")
    for item in data:
        if "service" in item:
            service = item["service"]
        else:
            logger.info(f"Object {item} has no associated service\n")
            continue
        if not rip.get_internal_services([service]): # check if the service is internal
            continue
        for value in values:
            if service not in return_dict:
                return_dict[service] = {value: [item[value]]}
            else:
                if value in return_dict[service]:
                    return_dict[service][value].append(item[value])
                else:
                    return_dict[service][value] = [item[value]]
    
    logger.info(f"Created dictionary:\n{return_dict}")
    return return_dict

def get_edges_milestone_task(choice, all_rms_data=None):
    if all_rms_data is None:
        all_rms_data = {}
    if choice == RmsEndpoint.EDGES:
        all_rms_data[choice.value] = get_cpt_data([RmsEndpoint.EDGES.value])[0]
    elif choice == RmsEndpoint.MILESTONES:
        all_rms_data[choice.value] = get_cpt_data([RmsEndpoint.MILESTONES.value])[0]
    elif choice == RmsEndpoint.TASKS:
        all_rms_data[choice.value] = get_cpt_data([RmsEndpoint.TASKS.value])[0]

def get_cpt_data(endpoints: Iterable[str]) -> Iterable[Dict[str, str]]:
    logger = get_logger()
    rmsv2_auth = get_aws_auth(AWS_HOST_RMSV2, AWS_REGION_EAST)
    fetched_data = []
    for endpoint in endpoints:
        kwargs = {"label": "COMMERCIAL_PARTITION_TEMPLATE"} if endpoint == RmsEndpoint.EDGES.value else {"dimension": "COMMERCIAL_PARTITION_TEMPLATE"}
        fetched_data.append(get_rms_data(AWS_HOST_RMSV2, rmsv2_auth, endpoint, **kwargs))
    
    logger.info(f"Data retrieved:\n{fetched_data}")
    return fetched_data

def get_rms_data(aws_host: str, auth: AWSRequestsAuth, endpoint: str, **kwargs):
    data = []
    logger = get_logger()
    query_params = urllib.parse.urlencode(kwargs)
    url = urllib.parse.urlunparse(("https", aws_host, f"prod/{endpoint}", None, query_params, None))
    json_object, next_token = get_rms_response(auth, url)
    data.extend(json_object[endpoint])
    while next_token:
        logger.info(f"Sending request to fetch data from RMSV2 commercial partition template with token {next_token}...")
        json_object, next_token = get_rms_response(auth, url, next_token)
        data.extend(json_object[endpoint])
    return data

def get_rms_response(rmsauth: AWSRequestsAuth, url: str, next_token=None):
    url = url_token_checker(url, next_token)
    logger = get_logger()
    response = retry_get_requests(url, auth=rmsauth)
    json_object = None
    try: 
        response.raise_for_status()
        json_object = response.json()
        next_token = json_object.get("nextToken")
        logger.info(f"RMS response received:\n{json_object}")
    except requests.exceptions.HTTPError as e: 
        logger.error(response.raise_for_status())
        next_token = None

    return json_object, next_token
