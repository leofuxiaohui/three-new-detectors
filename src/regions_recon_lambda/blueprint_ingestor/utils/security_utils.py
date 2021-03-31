import os
from typing import Dict, Optional

from botocore.exceptions import ClientError

from regions_recon_lambda.blueprint_ingestor.utils.client_utils import get_honeycode_client


def get_honeycode_client_from_event(event: Dict[str, any]) -> Optional:
    if 'arn' in event:
        try:
            return get_honeycode_client(event['arn'])
        except ClientError:
            return None

    return get_honeycode_client(os.environ["BLUEPRINT_ARN"])
