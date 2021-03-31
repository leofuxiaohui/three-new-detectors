from typing import List

import pydash
from regions_recon_python_common.buildables_dao_models.region_metadata import RegionMetadata
from regions_recon_python_common.query_utils.region_metadata_query_utils import get_region_metadata
from regions_recon_python_common.utils.log import get_logger
from regions_recon_python_common.utils.misc import execute_retryable_call
from regions_recon_python_common.utils.cloudwatch_metrics_utils import submit_cloudwatch_metrics, increment_metric
from regions_recon_python_common.message_multiplexer_helper import MessageMultiplexerHelper, get_mm_endpoint
from regions_recon_python_common.utils.rms_managed_regions import get_regions_within_ninety_business_days_post_launch

from regions_recon_lambda.utils.launch_date_mailer_templates import (get_14_days_template, get_0_days_template,
                                                                     get_past_1_days_template, get_past_4_days_template,
                                                                     get_fallback_header)
from boto3.dynamodb.conditions import Key, Attr
from datetime import datetime, timezone, timedelta, date
from dateutil import parser
from traceback import format_exc
from enum import Enum
import pytz
import boto3
import json
import os
import coral
import copy

logger = get_logger()

CONDENSED_DATE_FORMAT = "%Y-%m-%d"
NORMALIZED_DATE_FORMAT = "%Y-%m-%d %H:%M %Z"
NORMALIZED_DATE_FORMAT_WITH_SEC = "%Y-%m-%d %H:%M:%S %Z"
CC_TEAM = "global-product-expansion"
NOTIFS = "notifications"
GM_ALIAS = "gm"
VP_ALIAS = "vp"
GM_NAME = "gm_name"
VP_NAME = "vp_name"
MAX_MSG_GROUP_LENGTH = 511

# These are the same but not dependent on each other
CC_TEAM_2 = "delivery-date-awareness"
GROUP_PREFIX = "delivery-date-awareness"


class NotificationState(Enum):
    NOT_NOTIFIED = 0
    LEFT_14 = 1
    LEFT_7 = 2
    LEFT_0 = 3
    PAST_1 = 4
    PAST_4x = 5


TO_FALLBACK_ORDER = {
    NotificationState.LEFT_14.value: [NOTIFS, GM_ALIAS, VP_ALIAS],
    NotificationState.LEFT_7.value: [NOTIFS, GM_ALIAS, VP_ALIAS],
    NotificationState.LEFT_0.value: [NOTIFS, GM_ALIAS, VP_ALIAS],
    NotificationState.PAST_1.value: [GM_ALIAS, NOTIFS, VP_ALIAS],
    NotificationState.PAST_4x.value: [VP_ALIAS, GM_ALIAS, NOTIFS]
}


TEMPLATE_MAP = {
    NotificationState.LEFT_14.value: get_14_days_template,
    NotificationState.LEFT_7.value: get_14_days_template,
    NotificationState.LEFT_0.value: get_0_days_template,
    NotificationState.PAST_1.value: get_past_1_days_template,
    NotificationState.PAST_4x.value: get_past_4_days_template
}


# Entry point
def notification_mailer(event, context):
    ddb = boto3.resource("dynamodb", region_name='us-east-1').Table(os.environ["BUILDABLES_TABLE_NAME"])
    mm_helper = MessageMultiplexerHelper(endpoint=get_mm_endpoint(os.environ["MM_STAGE"]),
                                         own_account_number=os.environ["ACCOUNT_ID"])
    notification_mailer_internal(event, context, ddb, mm_helper)

# The "true" portion of the script.  Took a page out of the backend's book for "request_handling"
# Having an internal handler helps with not mucking up unit testing more
def notification_mailer_internal(event, context, ddb, mm_helper):
    logger.info("event: {}".format(event))
    logger.info("context: {}".format(context.__dict__))

    metrics = {
        "message_send_success": 0,
        "message_send_failure": 0
    }

    notifications = {}
    services = {}

    notifications = _get_notifications(ddb, notifications)

    regions = get_recon_managed_regions()

    services = _get_services(ddb, services, notifications, regions)

    # No services need notifying so submit 0-0 metrics and end
    if not services:
        submit_cloudwatch_metrics(metrics_dict=metrics, service_name=context.function_name)
        return

    # remove feature flag after these are done: RECON-6219 and RECON-6220
    if os.environ["MM_STAGE"] != "prod" and os.environ["MM_STAGE"] != "gamma":
        services = _get_contacts_beta(ddb, services)
    else:
        services = _get_contacts_prod(ddb, services)

    for service in services:
        for state in services[service]["states"]:

            state_dict = services[service]["states"][state]

            if state_dict["value"] == 0:
                logger.error("A service that did not need to send mail was about to send mail!")
                logger.error("Service: {}".format(services[service]))
                raise Exception("Service with NOT_NOTIFIED state tried to send mail!")
            if state_dict["value"] < 0 or state_dict["value"] > 5:
                logger.error("Service: {}".format(services[service]))
                raise Exception("A service's notification state fell out of range!")

            contact, template, endpoint_params = _get_contact_template_endpoint(services[service], state_dict)

            if contact:
                metrics = _send_mail(ddb, notifications, services[service], state_dict, contact, template,
                                     endpoint_params, mm_helper, metrics)

    submit_cloudwatch_metrics(metrics_dict=metrics, service_name=context.function_name)


def get_rip_name_from_notification_instance(instance):
    return instance.split("-")[2]


def get_region_from_notification_instance(instance):
    return instance.split("-")[3]


def get_corresponding_plan(ddb, notification_instance):
    rip = get_rip_name_from_notification_instance(notification_instance)
    region = get_region_from_notification_instance(notification_instance)
    plan_instance = "{}:v0:{}".format(rip, region)

    query_params = {
        "ConsistentRead": False,
        "KeyConditionExpression": Key("artifact").eq("SERVICE") & Key("instance").eq(plan_instance)
    }
    items = _query_ddb(ddb, query_params)

    if len(items) > 0:
        return items[0]

    return {}


def dates_equal(plan_date, notification_date):
    return (datetime.strptime(plan_date, CONDENSED_DATE_FORMAT).date() - datetime.strptime(notification_date, CONDENSED_DATE_FORMAT).date()).days == 0


def update_notification_as_not_notified(ddb, notification_instance, plan_date):
    try:
        params = dict(
            Key={
                "artifact": "NOTIFICATION",
                "instance": notification_instance
            },
            UpdateExpression="set #s=:s, #l=:l",
            ExpressionAttributeNames={
                "#s": "state",
                "#l": "last_known_launch_date"
            },
            ExpressionAttributeValues={
                ":s": "NOT_NOTIFIED",
                ":l": plan_date
            },
            ReturnValues="UPDATED_NEW"
        )
        response = ddb.update_item(**params)
        logger.info("Successfully updated NOTIFICATION entry with {}: {}".format(params, response))

    except Exception as e:
        logger.exception("Unable to update notification with '{}': ".format(params))


def check_date_slip(ddb, notification):
    notification_date = notification["last_known_launch_date"]
    plan = get_corresponding_plan(ddb, notification["instance"])
    plan_date = plan.get("date", None)

    if plan_date and not dates_equal(plan_date, notification_date):
        logger.info("Notification object {} has an old date: {}, new date is: {} and needs to be updated".format(notification["instance"], notification_date, plan_date))
        update_notification_as_not_notified(ddb, notification["instance"], plan_date)
        return True

    return False


# Gather all NOTIFICATION artifacts from ddb related to delivery dates
def _get_notifications(ddb, notifications):
    query_params = {
        "ConsistentRead": False,
        "KeyConditionExpression": Key("artifact").eq("NOTIFICATION"),
        "FilterExpression": Attr("type").eq("delivery")
    }
    items = _query_ddb(ddb, query_params)

    try:
        for item in items:
            if not check_date_slip(ddb, item):
                notification = {
                    "instance": item["instance"],
                    "updated": item["updated"],
                    "state": item["state"],
                    "type": item["type"],
                    "retries": int(item["retries"])
                }
                notifications[notification["instance"]] = notification

        return notifications

    except Exception as e:
        logger.exception("Zero or incorrect NOTIFICATION items were returned from query: ")


def get_airport_codes(region_metadata_items: List[RegionMetadata]):
    return [region.airport_code for region in region_metadata_items]


def get_recon_managed_regions():
    # we only want to mail on regions 90 days post launch
    region_metadata = get_region_metadata()
    rms_managed_regions = get_regions_within_ninety_business_days_post_launch(region_metadata)

    return pydash.difference(get_airport_codes(region_metadata), get_airport_codes(rms_managed_regions))


# Gather all relevant service instances, checking when their delivery date is, comparing to related NOTIFICATION
def _get_services(ddb, services, notifications, regions):
    query_params = {
        "ConsistentRead": False,
        "KeyConditionExpression": Key("artifact").eq("SERVICE"),
        "FilterExpression": (
            Attr("version_instance").eq(0) &
            Attr("status").ne("GA") &
            Attr("status").ne("NOT_PLANNED") &
            Attr("date").exists()
        )
    }
    items = _query_ddb(ddb, query_params)

    try:
        for item in items:
            complete = False
            if "confidence" in item.keys():
                complete = True if item["confidence"] == "Complete" else False
                
            region = _get_region_from_instance_item(item)
            if region in regions and not complete:
                rip = _get_rip_from_instance_item(item)
                notification_name = "delivery-date-{}-{}".format(rip, region)

                days_left = (datetime.strptime(item["date"], CONDENSED_DATE_FORMAT).date() - datetime.now(pytz.timezone('US/Pacific')).date()).days
                
                state = _determine_state(days_left)

                services = _fill_services(notification_name, notifications, state, rip,
                                          services, region, days_left, item)
        return services
            
    except Exception as e:
        logger.exception("Zero or incorrect SERVICE items were returned from query: ")


def _get_contacts_prod(ddb, services):
    for service in services:
        instance_name = "{}:v0".format(services[service]["rip"])
        response = ddb.get_item(Key={"artifact": "SERVICE", "instance": instance_name})
        item = response["Item"]

        try:
            # Get name for prettier emails since some teams do not go by their RIP ID
            services = _get_service_name(item, services, service)

            contacts = {}
            contact_item = item.get("contacts", {})

            for contact in contact_item:
                contacts[contact] = contact_item[contact]

            if "plan" in item.keys():
                services[service]["contacts"] = contacts

        except Exception as e:
            logger.exception("Zero or incorrect SERVICE metadata items were returned from query: ")    

    return services


def _get_contacts_beta(ddb, services):
    for service in services:
        instance_name = "{}:v0".format(services[service]["rip"])

        response = ddb.get_item(Key={"artifact": "CONTACTS", "instance": instance_name})
        contact_item = response.get('Item')
        contacts = format_contacts(contact_item) if contact_item else {}

        response = ddb.get_item(Key={"artifact": "SERVICE", "instance": instance_name})
        service_item = response["Item"]

        try:
            # Get name for prettier emails since some teams do not go by their RIP ID
            services = _get_service_name(service_item, services, service)

            if "plan" in service_item.keys():
                services[service]["contacts"] = contacts

        except Exception as e:
            logger.exception("Zero or incorrect SERVICE metadata items were returned from query: ")    

    return services


def get_leader_name_from_leadership_chain(alias, leadership_chain):
    leader_dict = next(leader for leader in leadership_chain if leader["alias"] == alias)
    if leader_dict:
        return leader_dict["first_name"]
    return "Service Leader"


def format_contacts(contact_item):
    contacts = {}
    notifications_alias = contact_item.get(NOTIFS)
    gm_alias = contact_item.get(GM_ALIAS)
    vp_alias = contact_item.get(VP_ALIAS)
    leadership_chain = contact_item.get("leadership_chain")

    if notifications_alias:
        contacts[NOTIFS] = notifications_alias
    if gm_alias:
        contacts[GM_NAME] = get_leader_name_from_leadership_chain(gm_alias, leadership_chain)
        contacts[GM_ALIAS] = gm_alias
    if vp_alias:
        contacts[VP_NAME] = get_leader_name_from_leadership_chain(vp_alias, leadership_chain)
        contacts[VP_ALIAS] = vp_alias

    return contacts

def create_msg_group_name(contact):
    grp_name = GROUP_PREFIX + "-to-" + contact["TO"][0]
    if len(contact["CC"]) > 0:
        grp_name += "-cc-"
        for alias in contact["CC"]:
            grp_name = grp_name + alias + "-"
        grp_name = grp_name[:-1]
    return grp_name[:MAX_MSG_GROUP_LENGTH]


def get_contact_names(contacts):
    # remove feature flag after these are done: RECON-6219 and RECON-6220
    if os.environ["MM_STAGE"] != "prod" and os.environ["MM_STAGE"] != "gamma":
        gm = contacts[GM_NAME] if GM_NAME in contacts else "L8"
        vp = contacts[VP_NAME] if VP_NAME in contacts else "L10"
    else:
        gm = contacts[GM_ALIAS] if GM_ALIAS in contacts else "L8"
        vp = contacts[VP_ALIAS] if VP_ALIAS in contacts else "L10"

    return gm, vp


# Attempts to send one contact one template style of mail
def _send_mail(ddb, notifications, service, state, contact, template, endpoint_params, mm_helper, metrics):
    msg_group_name = create_msg_group_name(contact)
    message_group_arn = mm_helper.get_own_message_group_arn(message_group_name=msg_group_name)

    _prepare_mm_target(message_group_arn, contact, endpoint_params, msg_group_name, template, mm_helper)

    regions = []
    for region in state["regions"].values():
        regions.append(region)
    regions = sorted(regions, key=lambda item: item["region"])
    gm, vp = get_contact_names(service["contacts"])

    params = {
        "message_group_name": msg_group_name,
        "params": json.dumps({
            "name_rip": service["rip"],
            "name_long": service["name"],
            "l8": gm,
            "l10": vp,
            "regions": regions
        })
    }

    try:
        logger.info("sending message to {} stage with payload: {} ".format(contact, params))
        response = mm_helper.perform_operation(operation="send_message", params=params, convert_message_group_name=True)

        logger.info("sent mail! {}".format(response))
        metrics = increment_metric(metrics, "message_send_success")

        for region in state["regions"]:
            _update_notification(ddb, service, state, state["regions"][region], 0)

    except Exception as e:
        logger.exception("unable to send message: '{}': ".format(params))
        metrics = increment_metric(metrics, "message_send_failure")
        if notification["retries"]+1 >= 3:
            metrics = _send_fallback(service, state, contact, template, mm_helper, metrics)
        for region in state["regions"]:
            notification = notifications["delivery-date-{}-{}".format(service["rip"], region)]
            _update_notification(ddb, service, state, state["regions"][region], notification["retries"]+1)
    return metrics


# After 3 tries at sending mail and failing, send it to global expansion team
def _send_fallback(service, state, contact, template, mm_helper, metrics):
    msg_group_name = GROUP_PREFIX+"-"+CC_TEAM
    message_group_arn = mm_helper.get_own_message_group_arn(message_group_name=msg_group_name)
    endpoint_params = dict(
            EMAIL_SUBJECT="Please Forward: Action Requested for Scheduled Launch".format(state["value"]),
            EMAIL_SHORT_NAME="Recon"
        )
    template = get_fallback_header() + template
    _prepare_mm_target(message_group_arn, CC_TEAM, endpoint_params, msg_group_name, template, mm_helper)
    gm, vp = get_contact_names(service["contacts"])

    params = {
        "message_group_name": msg_group_name,
        "params": json.dumps({
            "name_rip": service["rip"],
            "name_long": service["name"],
            "l8": gm,
            "l10": vp,
            "regions": state["regions"],
            "contact": contact
        })
    }

    try:
        logger.info("sending message to {} stage with payload: {} ".format(CC_TEAM, params))
        response = mm_helper.perform_operation(operation="send_message", params=params, convert_message_group_name=True)

        logger.info("sent mail! {}".format(response))
        metrics = increment_metric(metrics, "message_send_success")

    except Exception as e:
        logger.exception("unable to send message: '{}': ".format(params))
        metrics = increment_metric(metrics, "message_send_failure")
    
    logger.debug("metrics in fallback: {}".format(metrics))
    return metrics


# Checks that the target group exists and updates its template, creates target if it did not exist
def _prepare_mm_target(message_group_arn, contact, endpoint_params, msg_group_name, template, mm_helper):
    target_name = msg_group_name
    email_endpoint = format_endpoint(contact)
    target_params = {
        "message_group_arn": message_group_arn,
        "channel": "email",
        "endpoint": email_endpoint,
        "endpoint_params": endpoint_params,
        "message_template_type": "mustache",
        "message_template_name": target_name,
        "message_template": template
    }
    existing_target_arn = None
    try:
        mm_helper.perform_operation(operation="get_message_group", params={"message_group_arn": message_group_arn})
    except coral.exceptions.CoralClientException:
        # This exception should only occur once per contact
        logger.warning("{} message group does not exist!  Creating it and its target now...".format(msg_group_name))
        mm_helper.perform_operation(operation="create_message_group", params={"message_group_name": msg_group_name})

    msg_group = mm_helper.perform_operation(operation="get_message_group", params={"message_group_arn": message_group_arn})
    for target_arn, target_obj in msg_group.message_group.targets.items():
        if target_obj.target_name == target_name:
            existing_target_arn = target_arn
            break

    if existing_target_arn is not None:
        target_params["target_arn"] = existing_target_arn
        logger.warning("UPDATING target {} with params {}".format(target_name, target_params))
        mm_helper.perform_operation(operation="update_target", params=target_params)
    else:
        target_params["target_name"] = target_name
        logger.warning("CREATING target {} with params {}".format(target_name, target_params))
        mm_helper.perform_operation(operation="create_target", params=target_params)


def format_endpoint(contact):
    email_endpoint = copy.deepcopy(contact)
    for key in email_endpoint:
        for index, alias in enumerate(email_endpoint[key]):
            email_endpoint[key][index] = alias + "@amazon.com"
    return json.dumps(email_endpoint)


def _get_contact_template_endpoint(service, state):
    # Since we only kept services that need to be notified, we know state.value can only be 1 - 5
    contacts_dict = service["contacts"]
    if not contacts_dict:
        return None, None, None

    notif_state = state['value']

    to_order = TO_FALLBACK_ORDER[notif_state]
    template = TEMPLATE_MAP[notif_state]()

    contact = {
        "TO": [],
        "CC": [CC_TEAM]
    }

    for key in to_order:
        if key in contacts_dict and contacts_dict[key]:
            contact["TO"].append(contacts_dict[key])
            break

    contact = add_aliases_to_cc(notif_state, contacts_dict, contact)

    if len(contact["TO"]) == 0:
        contact = None

    endpoint_params = dict(
        EMAIL_SUBJECT="Notification {}: Action Requested for Scheduled Launch".format(notif_state),
        EMAIL_SHORT_NAME="Recon"
    )

    if os.environ["MM_STAGE"] != "prod":
        contact = {
            "TO": ["region-updates-test"],
            "CC": []
        }
        endpoint_params = dict(
            EMAIL_SUBJECT="Delivery Date Email Notification Test - {}".format(os.environ["MM_STAGE"]),
            EMAIL_SHORT_NAME="ReconTest"
        )

    return contact, template, endpoint_params


def add_aliases_to_cc(notif_state, contacts_dict, contact):
    if (notif_state == NotificationState.PAST_1.value):
        contact["CC"].append(CC_TEAM_2)

        if NOTIFS in contacts_dict:
            contact["CC"].append(contacts_dict[NOTIFS])

    elif (notif_state == NotificationState.PAST_4x.value):
        contact["CC"].append(CC_TEAM_2)

        if NOTIFS in contacts_dict:
            contact["CC"].append(contacts_dict[NOTIFS])

        if GM_ALIAS in contacts_dict:
            contact["CC"].append(contacts_dict[GM_ALIAS])
    return contact


def _update_notification(ddb, service, state, region, retries):
    try:
        params = dict(
            Key={
                "artifact": "NOTIFICATION",
                "instance": "delivery-date-{}-{}".format(service["rip"], region["region"])
            },
            UpdateExpression="set updated=:u, #s=:s, #t=:t, retries=:r, #l=:l",
            ExpressionAttributeNames={
                "#s": "state",
                "#t": "type",
                "#l": "last_known_launch_date"
            },
            ExpressionAttributeValues={
                ":u": datetime.now(timezone.utc).strftime(NORMALIZED_DATE_FORMAT_WITH_SEC),
                ":s": state["name"],
                ":t": "delivery",
                ":r": retries,
                ":l": region["date"]
            },
            ReturnValues="UPDATED_NEW"
        )
        response = ddb.update_item(**params)
        logger.info("Successfully updated NOTIFICATION entry with {}: {}".format(params, response))

    except Exception as e:
        logger.exception("Unable to update notifications with '{}': ".format(params))


def _determine_state(days_left):
    if days_left <= -4:
        return NotificationState.PAST_4x
    elif days_left <= -1:
        return NotificationState.PAST_1
    elif days_left == 0:
        return NotificationState.LEFT_0
    elif days_left <= 7:
        return NotificationState.LEFT_7
    elif days_left <= 14:
        return NotificationState.LEFT_14
    else:
        return NotificationState.NOT_NOTIFIED


def multiple_of_4_days_past(days_left):
    return days_left < 0 and ((days_left * -1) % 4) == 0 


def _fill_services(notification_name, notifications, state, rip, services, region, days_left, item):
    if state.name == "NOT_NOTIFIED":
        return services
    # Only items that need to be notified are tracked kept
    if notifications and notification_name in notifications:
        noted_name = notifications[notification_name]["state"]
    else:
        noted_name = "Notification does NOT exist"

    if (noted_name != state.name) or (noted_name == NotificationState.PAST_4x.name and multiple_of_4_days_past(days_left)):
        # Bit of a large nesting of dicts, but helps with some iteration
        # later regarding who to sendwhat template of mail
        if not services or rip not in services:
            services[rip] = dict(
                rip=rip,
                name=rip,
                states={},
                contacts={}
            )

        states_dict = services[rip]["states"]

        if not states_dict or state.name not in states_dict:
            states_dict[state.name] = dict(
                name=state.name,
                value=state.value,
                regions={}
            )

        updated = None
        if "updated" in item.keys():
            updated = (item["updated"].split("T"))[0]

        note = None
        if "note" in item.keys():
            note = item["note"]

        updater = None
        if "updater" in item.keys():
            updater = item["updater"]

        states_dict[state.name]["regions"][region] = dict(
            region=region,
            days_left=days_left,
            date=item["date"],
            note=note,
            updated=updated,
            updater=updater
        )
        services[rip]["states"] = states_dict
    return services


def _query_ddb(ddb, query_params):
    items = []
    while True:
        resp = execute_retryable_call(client=ddb, operation="query", **query_params)
        try:
            items += resp["Items"]
        except KeyError:
            pass
        try:
            query_params["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        except KeyError:
            break
    logger.debug("Returning {} items for query '{}'".format(len(items), query_params))
    return items


def _get_region_from_instance_item(item):
    instance_list = item["instance"].split(":")
    return instance_list[2] if len(instance_list) == 3 else "Not an instance"


def _get_rip_from_instance_item(item):
    return (item["instance"].split(":"))[0]


def _get_service_name(item, services, service):
    if "name_sortable" in item.keys():
        services[service]["name"] = item["name_sortable"]
    elif "name_long" in item.keys():
        services[service]["name"] = item["name_long"]
    return services