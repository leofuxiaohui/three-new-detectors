import boto3
import requests
import urllib
from requests.adapters import HTTPAdapter
from aws_requests_auth.aws_auth import AWSRequestsAuth
from requests.packages.urllib3.util.retry import Retry
from regions_recon_python_common.utils.log import get_logger

# Function to retry requests in case they fail
def retry_get_requests(url, auth):
    retry_strategy = Retry(
        total=10,
        status_forcelist=[429, 500, 502, 503, 504],
        method_whitelist=["HEAD", "GET", "OPTIONS"],
        backoff_factor=0.1,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    http = requests.Session()
    http.mount("https://", adapter)
    response = http.get(url, auth=auth)
    return response

def url_token_checker(url, next_token=None):
    if next_token:
        url = add_url_params(url, {"nextToken": next_token})
    return url

def get_aws_auth(aws_host, aws_region):
    logger = get_logger()
    session = boto3.Session()
    credentials = session.get_credentials()

    current_credentials = credentials.get_frozen_credentials()

    return AWSRequestsAuth(
        aws_access_key=current_credentials.access_key,
        aws_secret_access_key=current_credentials.secret_key,
        aws_token=current_credentials.token,
        aws_host=aws_host,
        aws_region=aws_region,
        aws_service="execute-api"
    )

def add_url_params(url, params):
    # Unquoting URL first so we don't loose existing args
    url = urllib.parse.unquote(url)
    # Extracting url info
    parsed_url = urllib.parse.urlparse(url)
    # Extracting URL arguments from parsed URL
    get_args = parsed_url.query
    # Converting URL arguments to dict
    parsed_get_args = dict(urllib.parse.parse_qsl(get_args))
    # Merging URL arguments dict with new params
    parsed_get_args.update(params)

    # Bool and Dict values should be converted to json-friendly values
    # you may throw this part away if you don't like it :)
    parsed_get_args.update(
        {k: json.dumps(v) for k, v in parsed_get_args.items() if isinstance(v, (bool, dict))}
    )

    # Converting URL argument to proper query string
    encoded_get_args = urllib.parse.urlencode(parsed_get_args, doseq=True)
    # Creating new parsed result object based on provided with new
    # URL arguments. Same thing happens inside of urlparse.
    new_url = urllib.parse.ParseResult(
        parsed_url.scheme,
        parsed_url.netloc,
        parsed_url.path,
        parsed_url.params,
        encoded_get_args,
        parsed_url.fragment,
    ).geturl()

    return new_url