import boto3
from aws_requests_auth.aws_auth import AWSRequestsAuth
from regions_recon_python_common.utils.log import get_logger

from regions_recon_lambda.utils.constants import AWS_RMS_ANALYTICS

logger = get_logger()


def get_rms_request_auth() -> AWSRequestsAuth:
    logger.debug("Getting frozen credentials using boto3")

    # Frozen credentials are needed to prevent a race condition when getting access / secret key
    frozen_credentials = boto3.Session().get_credentials().get_frozen_credentials()

    rms_request_auth = AWSRequestsAuth(
        aws_access_key=frozen_credentials.access_key,
        aws_secret_access_key=frozen_credentials.secret_key,
        aws_token=frozen_credentials.token,
        aws_host=AWS_RMS_ANALYTICS,
        aws_region="us-east-1",
        aws_service="execute-api"
    )

    logger.debug("Successfully received frozen credentials and created AWSRequestsAuth object")

    return rms_request_auth
