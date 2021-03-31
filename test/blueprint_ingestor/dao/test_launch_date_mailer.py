from moto import mock_dynamodb2
from mock import Mock, patch
from freezegun import freeze_time
from regions_recon_python_common.buildables_dao_models.region_metadata import RegionMetadata

from regions_recon_lambda.utils.launch_date_mailer_templates import (get_14_days_template, get_0_days_template,
                                                                     get_past_1_days_template, get_past_4_days_template,
                                                                     get_fallback_header)
import os
import boto3
import pytest
import json
import regions_recon_lambda.launch_date_mailer as launch_date_mailer

CONDENSED_DATE_FORMAT = "%Y-%m-%d"
NORMALIZED_DATE_FORMAT = "%Y-%m-%d %H:%M %Z"
NORMALIZED_DATE_FORMAT_WITH_SEC = "%Y-%m-%d %H:%M:%S %Z"
KEY_SCHEMA = [{"AttributeName": "artifact", "KeyType": "HASH"}, {"AttributeName": "instance", "KeyType": "RANGE"}]
MM_PATCH_STRING = "regions_recon_python_common.message_multiplexer_helper.MessageMultiplexerHelper"
CLOUDWATCH_PATCH_STRING = "regions_recon_lambda.launch_date_mailer.submit_cloudwatch_metrics"
CONTACT_PATCH_STRING = "regions_recon_lambda.launch_date_mailer._get_contacts_prod"
PREPARE_PATCH_STRING = "regions_recon_lambda.launch_date_mailer._prepare_mm_target"

def numeric_attribute(name):
  return {"AttributeName": name, "AttributeType": "N"}

def string_attribute(name):
  return {"AttributeName": name, "AttributeType": "S"}

ATTRIBUTE_DEFINITIONS=[
    string_attribute("artifact"),
    string_attribute("instance"),
]

NOTIFICATION_ITEM = {
    "artifact": "NOTIFICATION",
    "instance": "delivery-date-lol-kek",
    "updated": "2020-01-01 14:29:15 UTC",
    "state": "NOT_NOTIFIED",
    "type": "delivery",
    "retries": 0,
    "last_known_launch_date": "2020-02-17"
}

INTERNAL_NOTFICATIONS = {
    "delivery-date-lol-kek": {
        "instance": "delivery-date-lol-kek",
        "updated": "2020-01-01 14:29:15 UTC",
        "state": "NOT_NOTIFIED",
        "type": "delivery",
        "retries": 0
    }
}

REGION_ITEM = {
    "artifact": "REGION",
    "instance": "kek:v0",
    "airport_code": "kek",
    "status": "GA",
    "version_instance": 0,
}

EXPECTED_SERVICE_ITEM = {
    "lol": {
        "rip": "lol",
        "name": "lol",
        "states": {
            "LEFT_14": {
                "name": "LEFT_14",
                "value": 1,
                "regions": {
                    "kek": {
                        "region": "kek",
                        "days_left": 14,
                        "date": "2020-02-17",
                        "note": "D flat",
                        "updated": "2020-02-10",
                        "updater": "me"
                    }
                }
            }
        },
        "contacts": {'gm': 'Jezos', 'notifications': 'lol', 'vp': 'Beff'}
    }
}

PLAN_ITEM = {
    "artifact": "SERVICE",
    "instance": "lol:v0:kek",
    "plan": "seek",
    "name_sortable": "Lots of Love",
    "contacts": {"gm": "Jezos", "vp": "Beff", "notifications": "lol"}
}

CONTACT_ITEM = {
    "notifications": "something_pm",
    "leadership_chain": [
        {
            "alias": "lol",
            "first_name": "blah"
        },
        {
            "alias": "kek",
            "first_name": "something"
        }
    ],
    "gm": "lol",
    "vp": "kek"
}


class Context(object):
    pass


@pytest.fixture
def mocked_environment_prod():
    mocked_environment_prod = patch.dict(os.environ, {"BUILDABLES_TABLE_NAME": "test",
                                                      "MM_STAGE": "prod",
                                                      "ACCOUNT_ID": "8675309"}
                                        )
    return mocked_environment_prod


@pytest.fixture
def mocked_environment_beta():
    mocked_environment_beta = patch.dict(os.environ, {"MM_STAGE": "beta"}
                                        )
    return mocked_environment_beta


@freeze_time("2020-02-03 14:05:06", tz_offset=0)
@mock_dynamodb2
def test_notification_mailer_internal(mocked_environment_prod):
    mocked_environment_prod.start()
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

    table = dynamodb.create_table(
        TableName=os.environ["BUILDABLES_TABLE_NAME"],
        KeySchema=KEY_SCHEMA,
        AttributeDefinitions=ATTRIBUTE_DEFINITIONS
    )

    # Combining the use of a service/region instance and service metadata due to limitation of mocking DDB, but
    # still provides proper expected outputs
    service_item = {
        "status": "PLANNED",
        "artifact": "SERVICE",
        "instance": "lol:v0:kek",
        "updated": "2020-02-10T12:00:30.952587",
        "updater": "me",
        "date": "2020-02-17",
        "confidence": "GREEN",
        "airport_code": "kek",
        "note": "D flat",
        "version_instance": 0,
        "contacts": {"gm": "Jezos", "vp": "Beff", "notifications": "lol"},
        "name_sortable": "Lots of Love",
        "plan": "hide"
    }

    table.put_item(Item=NOTIFICATION_ITEM)
    table.put_item(Item=REGION_ITEM)
    table.put_item(Item=service_item)

    conn = boto3.resource("dynamodb", region_name='us-east-1').Table(os.environ["BUILDABLES_TABLE_NAME"])
    mocked_mm_helper = Mock(return_value="I sent mail!")
    context = Context()
    context.function_name = "launch_date_mailer"

    expected_metrics = {"message_send_success": 1, "message_send_failure": 0}

    mocked_contacts_return = EXPECTED_SERVICE_ITEM
    mocked_contacts_return["lol"]["contacts"] = {"gm": "Jezos", "vp": "Beff", "notifications": "lol"}
    with patch(MM_PATCH_STRING, return_value=mocked_mm_helper):
        with patch(CLOUDWATCH_PATCH_STRING, autospec=True) as mocked_submit_cloudwatch_metrics:
            # Have to mock our own _get_contacts return value due to moto's mock ddb not allowing a service and a
            # service metadate item in the mocked table since they share the same "artifact" value of "SERVICE"
            with patch(CONTACT_PATCH_STRING, return_value=mocked_contacts_return):
                # _prepare_mm_target relies on MM, has to be patched as well
                with patch(PREPARE_PATCH_STRING, return_value=None):
                    with patch("regions_recon_lambda.launch_date_mailer.get_recon_managed_regions", return_value=["kek"]):
                        launch_date_mailer.notification_mailer_internal("An event has occured!", context, conn, mocked_mm_helper)
                        mocked_submit_cloudwatch_metrics.assert_called_once_with(metrics_dict=expected_metrics, service_name=context.function_name)
    # Return EXPECTED_SERVICE_ITEM to its initial version for other tests
    EXPECTED_SERVICE_ITEM["lol"]["contacts"] = {}


@mock_dynamodb2
@patch.object(launch_date_mailer, 'check_date_slip')
def test_get_notifications(mock_check_date_slip, mocked_environment_prod):
    mocked_environment_prod.start()
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

    table = dynamodb.create_table(
        TableName=os.environ["BUILDABLES_TABLE_NAME"],
        KeySchema=KEY_SCHEMA,
        AttributeDefinitions=ATTRIBUTE_DEFINITIONS
    )

    table.put_item(Item=NOTIFICATION_ITEM)
    
    conn = boto3.resource("dynamodb", region_name='us-east-1').Table(os.environ["BUILDABLES_TABLE_NAME"])
    mock_check_date_slip.return_value = False
    result = launch_date_mailer._get_notifications(conn, {})
    expected = INTERNAL_NOTFICATIONS
    mocked_environment_prod.stop()
    assert result == expected


@freeze_time("2020-02-03 14:05:06", tz_offset=0)
@mock_dynamodb2
def test_get_services(mocked_environment_prod):
    mocked_environment_prod.start()
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

    table = dynamodb.create_table(
        TableName=os.environ["BUILDABLES_TABLE_NAME"],
        KeySchema=KEY_SCHEMA,
        AttributeDefinitions=ATTRIBUTE_DEFINITIONS
    )

    notifications = INTERNAL_NOTFICATIONS

    item = {
        "status": "PLANNED",
        "artifact": "SERVICE",
        "instance": "lol:v0:kek",
        "updated": "2020-02-10T12:00:30.952587",
        "updater": "me",
        "date": "2020-02-17",
        "airport_code": "kek",
        "confidence": "GREEN",
        "note": "D flat",
        "version_instance": 0
    }

    table.put_item(Item=item)

    conn = boto3.resource("dynamodb", region_name='us-east-1').Table(os.environ["BUILDABLES_TABLE_NAME"])
    regions = ["kek"]
    result = launch_date_mailer._get_services(conn, {}, notifications, regions)
    expected = EXPECTED_SERVICE_ITEM
    mocked_environment_prod.stop()
    assert result == expected


@mock_dynamodb2
@patch.object(launch_date_mailer, 'format_contacts')
def test_get_contacts_beta(mock_format_contacts, mocked_environment_prod):
    mocked_environment_prod.start()
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

    table = dynamodb.create_table(
        TableName=os.environ["BUILDABLES_TABLE_NAME"],
        KeySchema=KEY_SCHEMA,
        AttributeDefinitions=ATTRIBUTE_DEFINITIONS
    )

    service_item = {
        "artifact": "SERVICE",
        "instance": "lol:v0",
        "plan": "seek",
        "name_sortable": "Lots of Love"
    }

    contact_item = {
        "artifact": "CONTACTS",
        "instance": "lol:v0"
    }

    table.put_item(Item=service_item)
    table.put_item(Item=contact_item)

    conn = boto3.resource("dynamodb", region_name='us-east-1').Table(os.environ["BUILDABLES_TABLE_NAME"])
    services = {
        "lol": {
            "rip": "lol",
            "name": "lol",
            "contacts": {}
        }
    }
    mock_format_contacts.return_value = {"gm": "Jezos", "vp": "Beff", "notifications": "lol"}

    result = launch_date_mailer._get_contacts_beta(conn, services)

    expected = {
        "lol": {
            "rip": "lol",
            "name": "Lots of Love",
            "contacts": {"gm": "Jezos", "vp": "Beff", "notifications": "lol"}
        }
    }
    mocked_environment_prod.stop()
    assert result == expected


@mock_dynamodb2
def test_get_contacts_prod(mocked_environment_prod):
    mocked_environment_prod.start()
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

    table = dynamodb.create_table(
        TableName=os.environ["BUILDABLES_TABLE_NAME"],
        KeySchema=KEY_SCHEMA,
        AttributeDefinitions=ATTRIBUTE_DEFINITIONS
    )

    item = {
        "artifact": "SERVICE",
        "instance": "lol:v0",
        "plan": "seek",
        "name_sortable": "Lots of Love",
        "contacts": {"gm": "Jezos", "vp": "Beff", "notifications": "lol"}
    }

    table.put_item(Item=item)

    conn = boto3.resource("dynamodb", region_name='us-east-1').Table(os.environ["BUILDABLES_TABLE_NAME"])
    services = {
        "lol": {
            "rip": "lol",
            "name": "lol",
            "contacts": {}
        }
    }

    result = launch_date_mailer._get_contacts_prod(conn, services)

    expected = {
        "lol": {
            "rip": "lol",
            "name": "Lots of Love",
            "contacts": {"gm": "Jezos", "vp": "Beff", "notifications": "lol"}
        }
    }
    mocked_environment_prod.stop()
    assert result == expected


@mock_dynamodb2
def test_send_mail(mocked_environment_prod):
    mocked_environment_prod.start()
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

    table = dynamodb.create_table(
        TableName=os.environ["BUILDABLES_TABLE_NAME"],
        KeySchema=KEY_SCHEMA,
        AttributeDefinitions=ATTRIBUTE_DEFINITIONS
    )

    conn = boto3.resource("dynamodb", region_name='us-east-1').Table(os.environ["BUILDABLES_TABLE_NAME"])

    notifications = INTERNAL_NOTFICATIONS
    notifications["delivery-date-lol-kek"]["date"] = "2020-12-30"
    notifications["delivery-date-lol-kek"]["state"] = "LEFT_14"

    service = {
        "rip": "lol",
        "name": "Lots of Love",
        "contacts": {"gm": "Jezos", "vp": "Beff", "notifications": "lol"}
    }
    region = {"region": "kek", "date": "2000-11-08"}
    state = {
        "name": "LEFT_14",
        "regions": {"kek": region},
        "value": 1
    }
    contact = {"TO": ["me"], "CC": []}
    template = get_14_days_template()
    endpoint_params = dict(
            EMAIL_SUBJECT="Notification {}: Action Requested for Scheduled Launch".format(state["value"]),
            EMAIL_SHORT_NAME="Recon"
        )
    metrics = {"message_send_success": 0, "message_send_failure": 0}
    mocked_mm_helper = Mock(return_value="I sent!")

    with patch(MM_PATCH_STRING, return_value=mocked_mm_helper):
        with patch(PREPARE_PATCH_STRING, return_value=None):
            result = launch_date_mailer._send_mail(conn, notifications, service, state, contact, template, endpoint_params,
                                                   mocked_mm_helper, metrics)
            expected = {"message_send_success": 1, "message_send_failure": 0}
            assert result == expected

    mocked_environment_prod.stop()


@patch.dict(os.environ, {'MM_STAGE': 'gamma'})
def test_send_fallback():
    service = {
        "rip": "lol",
        "name": "Lots of Love",
        "contacts": {"gm": "Jezos", "vp": "Beff", "notifications": "lol"}
        }
    region = {"region": "kek", "date": "2000-11-08"}
    state = {
        "name": "LEFT_14",
        "regions": {"kek": region},
        "value": 1
        }
    contact = "me"
    template = get_14_days_template()
    metrics = {"message_send_success": 0, "message_send_failure": 0}
    mocked_mm_helper = Mock(return_value="I sent!")

    with patch(MM_PATCH_STRING, return_value=mocked_mm_helper):
        with patch(PREPARE_PATCH_STRING, return_value=None):
            result = launch_date_mailer._send_fallback(service, state, contact, template, mocked_mm_helper, metrics)
            expected = {"message_send_success": 1, "message_send_failure": 0}
            assert result == expected


def test_get_contact_template_endpoint(mocked_environment_prod):
    mocked_environment_prod.start()

    service = {"contacts": {"notifications": "lol"}}
    state = {"value": 1}
    result = launch_date_mailer._get_contact_template_endpoint(service, state)
    endpoint_params = {"EMAIL_SUBJECT": "Notification 1: Action Requested for Scheduled Launch",
                       "EMAIL_SHORT_NAME": "Recon"}
    expected = ({"TO": ["lol"], "CC": ["global-product-expansion"]}, get_14_days_template(), endpoint_params)
    mocked_environment_prod.stop()
    assert result == expected


@pytest.mark.parametrize("notif_state, expected", [
    (4, {"TO": [], "CC": ["delivery-date-awareness", "lol"]}),
    (5, {"TO": [], "CC": ["delivery-date-awareness", "lol", "kek"]}),
    ])
def test_aliases_to_cc(notif_state, expected):
    contacts_dict = {"notifications": "lol", "gm": "kek"}
    contact = {"TO": [], "CC": []}

    result = launch_date_mailer.add_aliases_to_cc(notif_state, contacts_dict, contact)
    assert result == expected


@pytest.mark.parametrize("contact, expected", [
    ({"TO": ["yennua"], "CC": []}, "delivery-date-awareness-to-yennua"),
    ({"TO": ["yennua"], "CC": ["jeff"]}, "delivery-date-awareness-to-yennua-cc-jeff"),
    ({"TO": ["yennua"], "CC": ["jeff", "lol"]}, "delivery-date-awareness-to-yennua-cc-jeff-lol"),
    ])
def test_create_msg_group_name(contact, expected):
    result = launch_date_mailer.create_msg_group_name(contact)
    assert result == expected


@pytest.mark.parametrize("contact, expected", [
    ({"TO": ["yennua"]}, json.dumps({"TO": ["yennua@amazon.com"]})),
    ({"TO": ["yennua", "blah"], "CC": ["jeff"]}, json.dumps({"TO": ["yennua@amazon.com", "blah@amazon.com"], "CC": ["jeff@amazon.com"]})),
    ])
def test_format_endpoint(contact, expected):
    result = launch_date_mailer.format_endpoint(contact)
    assert result == expected


@mock_dynamodb2
def test_update_notification(mocked_environment_prod):
    mocked_environment_prod.start()
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

    table = dynamodb.create_table(
        TableName=os.environ["BUILDABLES_TABLE_NAME"],
        KeySchema=KEY_SCHEMA,
        AttributeDefinitions=ATTRIBUTE_DEFINITIONS
    )

    conn = boto3.resource("dynamodb", region_name='us-east-1').Table(os.environ["BUILDABLES_TABLE_NAME"])

    service = {"rip": "lol"}
    region = {"region": "kek", "date": "2020-02-17"}
    state = {"name": "LEFT_14"}

    launch_date_mailer._update_notification(conn, service, state, region, 0)
    mocked_environment_prod.stop()


@freeze_time("2020-02-03 04:05:06", tz_offset=0)
def test_determine_state_14():
    days_left = 14
    result = launch_date_mailer._determine_state(days_left)
    expected = launch_date_mailer.NotificationState.LEFT_14
    assert result == expected


@freeze_time("2020-02-03 04:05:06", tz_offset=0)
def test_determine_state_7():
    days_left = 7
    result = launch_date_mailer._determine_state(days_left)
    expected = launch_date_mailer.NotificationState.LEFT_7
    assert result == expected


def test_determine_state_0():
    days_left = 0
    result = launch_date_mailer._determine_state(days_left)
    expected = launch_date_mailer.NotificationState.LEFT_0
    assert result == expected


def test_determine_state_1():
    days_left = -1
    result = launch_date_mailer._determine_state(days_left)
    expected = launch_date_mailer.NotificationState.PAST_1
    assert result == expected


def test_determine_state_4():
    days_left = -4
    result = launch_date_mailer._determine_state(days_left)
    expected = launch_date_mailer.NotificationState.PAST_4x
    assert result == expected


def test_determine_state_not_notified():
    days_left = 15
    result = launch_date_mailer._determine_state(days_left)
    expected = launch_date_mailer.NotificationState.NOT_NOTIFIED
    assert result == expected


def test_fill_services():
    notification_name = "delivery-date-lol-kek"
    notifications = {
        "delivery-date-lol-kek": {
            "instance": "delivery-date-lol-kek",
            "updated": "2020-01-01 14:29:15 UTC",
            "state": "NOT_NOTIFIED"
        }
    }
    
    state = launch_date_mailer.NotificationState.LEFT_14
    rip = "lol"
    services = {}
    region = "kek"
    days_left = 14
    item = {
        "updated": "2020-02-10T12:00:30.952587",
        "updater": "me",
        "date": "2020-02-17",
        "note": "D flat"
    }
    result = launch_date_mailer._fill_services(notification_name, notifications, state,
                                               rip, services, region, days_left, item)
    expected = EXPECTED_SERVICE_ITEM
    assert result == expected


def test_fill_services_unneeded_service():
    notification_name = "delivery-date-lol-kek"
    notifications = INTERNAL_NOTFICATIONS
    state = launch_date_mailer.NotificationState.NOT_NOTIFIED
    rip = "lol"
    services = {}
    region = "kek"
    days_left = 14
    item = {
        "updated": "2020-02-10T12:00:30.952587",
        "updater": "me",
        "date": "2020-02-17",
        "note": "D flat"
    }
    result = launch_date_mailer._fill_services(notification_name, notifications, state,
                                               rip, services, region, days_left, item)
    expected = {}
    assert result == expected


def test_get_rip_name_from_notification_instance():
    notification_instance = "delivery-date-lol-kek"
    result = launch_date_mailer.get_rip_name_from_notification_instance(notification_instance)
    expected = "lol"
    assert result == expected


def test_get_region_from_notification_instance():
    notification_instance = "delivery-date-lol-kek"
    result = launch_date_mailer.get_region_from_notification_instance(notification_instance)
    expected = "kek"
    assert result == expected


def test_dates_equal_true():
    plan_date = "2019-07-05"
    notification_date = "2019-07-05"
    result = launch_date_mailer.dates_equal(plan_date, notification_date)
    assert result == True


def test_dates_equal_false():
    plan_date = "2019-07-07"
    notification_date = "2019-07-05"
    result = launch_date_mailer.dates_equal(plan_date, notification_date)
    assert result == False


@mock_dynamodb2
def test_get_corresponding_plan(mocked_environment_prod):
    mocked_environment_prod.start()
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

    table = dynamodb.create_table(
        TableName=os.environ["BUILDABLES_TABLE_NAME"],
        KeySchema=KEY_SCHEMA,
        AttributeDefinitions=ATTRIBUTE_DEFINITIONS
    )

    table.put_item(Item=PLAN_ITEM)

    conn = boto3.resource("dynamodb", region_name='us-east-1').Table(os.environ["BUILDABLES_TABLE_NAME"])
    notification_instance = "delivery-date-lol-kek"

    result = launch_date_mailer.get_corresponding_plan(conn, notification_instance)

    expected = PLAN_ITEM
    mocked_environment_prod.stop()
    assert result == expected


@mock_dynamodb2
@patch.object(launch_date_mailer, 'get_corresponding_plan')
@patch.object(launch_date_mailer, 'update_notification_as_not_notified')
def test_check_date_slip_true(mock_update_notification_as_not_notified, mock_get_corresponding_plan, mocked_environment_prod):
    mocked_environment_prod.start()
    conn = boto3.resource("dynamodb", region_name='us-east-1').Table(os.environ["BUILDABLES_TABLE_NAME"])
    notification = NOTIFICATION_ITEM

    plan = PLAN_ITEM
    plan["date"] = "2020-02-18"
    mock_get_corresponding_plan.return_value = plan
    result = launch_date_mailer.check_date_slip(conn, notification)
    mock_update_notification_as_not_notified.assert_called_once_with(conn, "delivery-date-lol-kek", "2020-02-18")

    assert result == True
    mocked_environment_prod.stop()


@mock_dynamodb2
@patch.object(launch_date_mailer, 'get_corresponding_plan')
def test_check_date_slip_false(mock_get_corresponding_plan, mocked_environment_prod):
    mocked_environment_prod.start()
    conn = boto3.resource("dynamodb", region_name='us-east-1').Table(os.environ["BUILDABLES_TABLE_NAME"])
    notification = NOTIFICATION_ITEM

    plan = PLAN_ITEM
    plan["date"] = "2020-02-17"
    mock_get_corresponding_plan.return_value = plan
    result = launch_date_mailer.check_date_slip(conn, notification)

    assert result == False
    mocked_environment_prod.stop()

@mock_dynamodb2
@patch.object(launch_date_mailer, 'get_corresponding_plan')
def test_check_date_slip_without_plan_date(mock_get_corresponding_plan, mocked_environment_prod):
    mocked_environment_prod.start()
    conn = boto3.resource("dynamodb", region_name='us-east-1').Table(os.environ["BUILDABLES_TABLE_NAME"])
    notification = NOTIFICATION_ITEM

    plan = PLAN_ITEM
    mock_get_corresponding_plan.return_value = plan
    result = launch_date_mailer.check_date_slip(conn, notification)

    assert result == False
    mocked_environment_prod.stop()


def test_format_contacts():
    expected = {
        "notifications": "something_pm",
        "gm": "lol",
        "vp": "kek",
        "gm_name": "blah",
        "vp_name": "something"
    }
    result = launch_date_mailer.format_contacts(CONTACT_ITEM)

    assert result == expected


def test_get_contact_names(mocked_environment_beta):
    mocked_environment_beta.start()

    contacts = {
        "notifications": "something_pm",
        "gm": "lol",
        "vp": "kek",
        "gm_name": "blah",
        "vp_name": "something"
    }

    expected = "blah", "something"

    result = launch_date_mailer.get_contact_names(contacts)

    assert result == expected


@pytest.mark.parametrize("days_left, expected", [
    (-4, True),
    (0, False),
    (-5, False),
    (4, False),
    (-8, True)
    ])
def test_multiple_of_4_days_past(days_left, expected):
    assert launch_date_mailer.multiple_of_4_days_past(days_left) == expected


@pytest.fixture
def stub_region_metadata():
    return [
        RegionMetadata(airport_code="IAD"),
        RegionMetadata(airport_code="CMH"),
        RegionMetadata(airport_code="ALE"),
        RegionMetadata(airport_code="KIX"),
        RegionMetadata(airport_code="PDT"),
    ]


def test_get_airport_codes(stub_region_metadata):
    assert set(launch_date_mailer.get_airport_codes(stub_region_metadata)) == {"IAD", "CMH", "ALE", "KIX", "PDT"}


@patch("regions_recon_lambda.launch_date_mailer.get_regions_within_ninety_business_days_post_launch")
@patch("regions_recon_lambda.launch_date_mailer.get_region_metadata")
def test_get_recon_managed_regions(mock_get_region_metadata, mock_get_regions_within_ninety_business_days_post_launch, stub_region_metadata):
    mock_get_region_metadata.return_value = stub_region_metadata

    mock_get_regions_within_ninety_business_days_post_launch.return_value = [
        RegionMetadata(airport_code="ALE"),
        RegionMetadata(airport_code="KIX"),
    ]

    assert set(launch_date_mailer.get_recon_managed_regions()) == {"IAD", "CMH", "PDT"}
