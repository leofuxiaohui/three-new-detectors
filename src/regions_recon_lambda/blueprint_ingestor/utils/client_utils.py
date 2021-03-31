import boto3
import os

HONEYCODE_REGION = 'us-west-2'

# See https://w.amazon.com/index.php/AWSAuth/STS/RegionalOnboarding#STS_Global_Endpoint_Deprecation_Policy_Engine_Violation
# We don't want to use the global (us-east-1) STS endpoint: creds are regional, so grab creds IN THE REGION where they
# will be used!
STS_ENDPOINT_URL = f'https://sts.{HONEYCODE_REGION}.amazonaws.com'


def get_honeycode_client(role_arn):
    sts_boto3_client = boto3.client(
        'sts',
        region_name=HONEYCODE_REGION,           # Honeycode only runs in us-west-2 currently, and this is where Blueprint lives
        endpoint_url=STS_ENDPOINT_URL)          # Ask for creds in the target region we will use them in

    blueprint_assumed_role = sts_boto3_client.assume_role(
        RoleArn=role_arn,
        RoleSessionName='Recon',
        DurationSeconds=900
    )

    credentials = blueprint_assumed_role['Credentials']

    return boto3.client('honeycode',
                        region_name=HONEYCODE_REGION,
                        aws_access_key_id=credentials['AccessKeyId'],
                        aws_secret_access_key=credentials['SecretAccessKey'],
                        aws_session_token=credentials['SessionToken']
                        )


def get_buildables_table():
    return boto3.resource('dynamodb', region_name='us-east-1').Table("buildables")
