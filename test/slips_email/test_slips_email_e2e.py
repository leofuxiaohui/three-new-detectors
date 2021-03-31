from freezegun import freeze_time
from datetime import datetime, timezone, timedelta
from moto import mock_dynamodb2, mock_cloudwatch
import os
import boto3
import yaml
from mock import Mock, patch
from regions_recon_lambda.slips_email.slips_email import send_slips_mail
from regions_recon_python_common.utils.log import get_logger

logger = get_logger()


def create_ddb_tables():
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    buildables = dynamodb.create_table(
        TableName='buildables',
        KeySchema=[ { 'AttributeName': 'artifact', 'KeyType': 'HASH' }, { 'AttributeName': 'instance', 'KeyType': 'RANGE' } ],
        AttributeDefinitions=[
            { 'AttributeName': 'artifact', 'AttributeType': 'S' },
            { 'AttributeName': 'instance', 'AttributeType': 'S' },
            { 'AttributeName': 'plan', 'AttributeType': 'S' },
        ],
        ProvisionedThroughput={ 'ReadCapacityUnits': 10, 'WriteCapacityUnits': 10 },
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'artifact-plan-index',
                'KeySchema': [ { 'AttributeName': 'artifact', 'KeyType': 'HASH' }, { 'AttributeName': 'plan', 'KeyType': 'RANGE' } ],
                'Projection': { 'ProjectionType': 'ALL' }
            }
        ]
    )

    yaml_filename = os.path.join(os.path.dirname(__file__), 'slips_email_e2e_db.yaml')
    with open(yaml_filename) as file:
        contents = yaml.safe_load(file)
        for item in contents['items']:
            buildables.put_item(Item=item)


@freeze_time("2020-05-01 04:05:06", tz_offset=0)
@mock_dynamodb2
@mock_cloudwatch
def test_slips_email_e2e():
    create_ddb_tables()
    mm_params = send_slips_mail({ 'debug': True, 'dryrun': True }, {})

    assert mm_params.get('beginning') == '2020-04-17'  # limit of how far we'll go back
    assert mm_params.get('end') == '2020-05-01' # basically when we ran (the latest day we care about)

    assert mm_params.get('slip_count') == 1
    assert mm_params.get('slips_exist') == True
    slip = mm_params['slips'][0]
    assert slip ==  {
                        'change': 85,
                        'current': '2020-04-26',
                        'name_pretty': 'chrisjen',
                        'name_rip': 'chrisjen',
                        'note': '',
                        'previous': '2020-02-01',
                        'region': 'ABC',
                        'updated': '2020-04-26',
                        'updater': 'john'
                    }

    assert mm_params.get('improvement_count') == 1
    assert mm_params.get('improvements_exist') == True
    improvement = mm_params['improvements'][0]
    assert improvement == {
                            'change': 33,
                            'current': '2020-03-10',
                            'name_pretty': 'chrisjen',
                            'name_rip': 'chrisjen',
                            'note': '',
                            'previous': '2020-04-12',
                            'region': 'DEF',
                            'updated': '2020-04-26',
                            'updater': 'moe'
                        }

    assert mm_params.get('unplanned_count') == 2
    assert mm_params['unplanned'] == [
        {
            'has_notes': False,
            'name_pretty': 'klaes',
            'name_rip': 'klaes',
            'regions': [ { 'region': 'ABC', 'separator': ',' }, { 'region': 'DEF', 'separator': '' } ]
        },
        {
            'has_notes': False,
            'name_pretty': 'sadavir',
            'name_rip': 'sadavir',
            'regions': [ { 'region': 'ABC', 'separator': ',' }, { 'region': 'DEF', 'separator': '' } ]
        }
    ]

    # assert 1 == 2 # uncomment to see logger messages
