from typing import Dict

from regions_recon_python_common.utils.log import get_logger
from regions_recon_python_common.utils.cloudwatch_metrics_utils import submit_cloudwatch_metrics, merge_metrics_dicts, increment_metric
from regions_recon_python_common.message_multiplexer_helper import MessageMultiplexerHelper, get_mm_endpoint
from regions_recon_python_common.utils.misc import get_rip_name_from_instance_field
from boto3.dynamodb.conditions import Key, Attr
from datetime import datetime, timezone, timedelta
from dateutil import parser
from traceback import format_exc
import pytz
import boto3
import json
import os

from regions_recon_python_common.utils.object_utils import deep_get

logger = get_logger()

# In hours.
TIME_HORIZON = int(os.environ["TIME_HORIZON"])
CONDENSED_DATE_FORMAT = "%Y-%m-%d"
NORMALIZED_DATE_FORMAT = "%Y-%m-%d %H:%M %Z"
NORMALIZED_DATE_FORMAT_WITH_SEC = "%Y-%m-%d %H:%M:%S %Z"
MM_STAGE = os.environ["MM_STAGE"]

def belongs_to_region(item):
    return item.get("belongs_to_artifact", {}).get("S") == "REGION"

def remove_system_updates(service, region):
    """ Removes updates from 'system'. This may leave dangling 'version_latest' references. """
    real_updates = []
    system_updates = 0
    seen = set()

    try:
        for index, update in service["regions"][region]["history"].items():
            if update["updater"]["S"] == "system":
                system_updates += 1
            else:
                instance = update["instance"]["S"]
                if instance not in seen:
                    seen.add(instance)
                    real_updates.append(update)

        if system_updates:
            logger.warn("REMOVED {} 'system' updates from {} in {}".format(system_updates, get_rip_name_from_instance_field(service["instance"]["S"]), region))

        if len(real_updates):
            real_updates = sorted(real_updates, key=lambda item: item["updated"])
            new_history = {0: real_updates[-1]}
            i = 1
            for item in real_updates:
                new_history[i] = item
                i += 1
            service["regions"][region]["history"] = new_history
        else:
            service["regions"][region]["history"] = []

    except Exception as e:
        logger.error("REBUILD EXCEPTION: {}\n{}".format(repr(e), format_exc()))


def get_confidence(update):
    confidence = ""
    if "confidence" in update:
        confidence = update["confidence"]["S"]

    if "status" in update:
        if update["status"]["S"] == "GA":
            confidence = "Complete"
        elif confidence == "":
            confidence = update["status"]["S"]

    return confidence

def condense_date_text(text):
    return parser.parse(text).strftime(CONDENSED_DATE_FORMAT)

def get_service_name(service):
    text = "[service name]"

    if "name_sortable" in service:
        text = service["name_sortable"]["S"]
    elif "name_sales" in service:
        text = service["name_sales"]["S"]
    elif "name_marketing" in service:
        text = service["name_marketing"]["S"]
    elif "name_long" in service:
        text = service["name_long"]["S"]
    elif "instance" in service:
        text = get_rip_name_from_instance_field(service["instance"]["S"])

    return text


def has_relevant_changes(history: Dict[any, any]) -> bool:
    # Will be tested in beta to try to remove the "changed_attributes" field
    # Unit tests will come after the beta flag is removed

    relevant_changes = ("date", "confidence", "note")
    latest_version: int

    try:
        latest_version = int(deep_get(history, (0, "version_latest", "N")))
    except ValueError:
        return False

    previous_item = history.get(latest_version - 1)
    if not previous_item:
        return False

    current_item = history[0]

    has_relevant_field_change = any(
                                     deep_get(current_item, (change, "S")) != deep_get(previous_item, (change, "S"))
                                     for change in relevant_changes
                                 )

    current_status = deep_get(current_item, ("status", "S"))

    has_status_change_to_GA = current_status != deep_get(previous_item, ("status", "S")) and current_status == "GA"

    result = has_relevant_field_change or has_status_change_to_GA
#     for debugging uncomment
#     print(f"Result of fields check : {has_relevant_field_change}")
#     print(f"Result of has_status_change_to_GA : {has_status_change_to_GA}")
#     print(f"Result of relevant_changes : {result}")
    
    return result


# Entry Point - Lambda starts here
def send_updates_mail(event, context):
    # In days.
    PAST_SYSTEM_EVENT_THRESHOLD = int(os.environ["PAST_SYSTEM_EVENT_THRESHOLD"])

    logger.info("event: {}".format(event))
    logger.info("context: {}".format(context.__dict__))

    metrics = {}
    metrics["message_send_success"] = 0
    metrics["message_send_failure"] = 0

    ddb = boto3.client("dynamodb", region_name='us-east-1')

    now = datetime.now(timezone.utc)
    notifications = {}
    update_limit = now - timedelta(hours=TIME_HORIZON)
    oldest_update = now
    table = os.environ["BUILDABLES_TABLE_NAME"]
    items = []
    services = {}

    try:
        response = ddb.query(
            TableName=table,
            KeyConditions={"artifact": {"ComparisonOperator": "EQ", "AttributeValueList": [{"S": "NOTIFICATION"}]}},
            QueryFilter={
                "type": {"ComparisonOperator": "EQ", "AttributeValueList": [{"S": "update"}]}
            }
        )

        if "Items" not in response.keys():
            logger.error("no NOTIFICATION artifacts are configured in the database, bozo")
        else:
            items = response["Items"]

        logger.info("STEP 1: regain our memory about the state of notifications")
        for item in items:
            # Protect ourselves from poorly formatted date values.
            updated = update_limit
            try:
                updated = (parser.parse(item["updated"]["S"])).replace(tzinfo=pytz.UTC)
                if updated < update_limit:
                    updated = update_limit
            except Exception as e:
                logger.error("could not parse date, IGNORE THIS IF WE ARE BOOTSTRAPPING: '{}': {}".format(item["updated"]["S"], e))
                updated = update_limit

            notification = {
                "instance": item["instance"]["S"],
                "updated": updated,
                "region": item["region"]["S"],
                "type": item["type"]["S"]
            }

            notifications[notification["region"]] = notification
            logger.info("NOTIFICATION: {}".format(notification))

            # Figure out how far back in time we need to look to satisfy whichever notification is the MOST out-of-date.
            # We don't want to have to make separate queries for every notification.
            if notification["updated"] < oldest_update:
                oldest_update = notification["updated"]

        logger.info("oldest_update: {}, update_limit {}".format(oldest_update, update_limit))

        logger.info("STEP 2: get list of services that have categories")
        try:
            total = 0
            args = dict(
                TableName=table,
                IndexName="artifact-plan-index",
                KeyConditions={
                    "artifact": {"ComparisonOperator": "EQ", "AttributeValueList": [{"S": "SERVICE"}]},
                },
                QueryFilter={
                    "version_instance": {"ComparisonOperator": "EQ", "AttributeValueList": [{"N": "0"}]}
                }
            )

            while True:
                response = ddb.query(**args)

                if "Items" not in response:
                    logger.error("no SERVICE instances returned")
                else:
                    items = response["Items"]
                    for item in items:
                        rip = (item["instance"]["S"].split(":"))[0]
                        if rip not in services:
                            services[rip] = dict(
                                # Raw items about each region for which we have data about this service.
                                regions={},

                                # Raw items about this service's non-regional data.
                                instances={}
                            )

                        if belongs_to_region(item):
                            # This is a region-specific item.
                            region = item["belongs_to_instance"]["S"]
                            if region in notifications:
                                if region not in services[rip]["regions"]:
                                    services[rip]["regions"][region] = dict(
                                        history={0: item},
                                        notification=notifications[region]
                                    )
                                services[rip]["regions"][region]["history"][int(item["version_instance"]["N"])] = item
                        else:
                            services[rip]["instances"][item["version_instance"]["N"]] = item

                    total += len(items)

                    if "LastEvaluatedKey" in response:
                        args["ExclusiveStartKey"] = response["LastEvaluatedKey"]
                    else:
                        break

            # DATA CLEANUP
            # There are some services without categories set on their non-regional instances. These are typically deprecated.
            # for now, we need to remove these as they will wreck the code later on and it's unclear how to "patch" the data
            # in an automated way that is helpful to the customer.
            delete = [key for key in services if len(services[key]["instances"]) == 0]
            logger.warn("CLEANUP: eliding services which lack proper category settings: {}".format(delete))
            for key in delete:
                del services[key]

            logger.info("{} SERVICES: {}".format(len(services), sorted(services.keys())))

            try:
                args = dict(
                    TableName=table,
                    IndexName="artifact-updated-index",
                    KeyConditions={
                        "artifact": {"ComparisonOperator": "EQ", "AttributeValueList": [{"S": "SERVICE"}]},
                        "updated": {"ComparisonOperator": "BETWEEN", "AttributeValueList": [{"S": oldest_update.isoformat()}, {"S": now.isoformat()}]}
                    },
                    QueryFilter={
                        "version_instance": {"ComparisonOperator": "EQ", "AttributeValueList": [{"N": "0"}]},
                    }
                )

                no_cat = 0
                service_specific = 0
                unconfig_region = 0
                unconfig_regions = []
                possibly_relevant = 0
                while True:
                    response = ddb.query(**args)

                    if "Items" not in response:
                        logger.info("STEP 3: no service updates since {}".format(oldest_update.strftime(NORMALIZED_DATE_FORMAT_WITH_SEC)))
                    else:
                        items = response["Items"]
                        logger.info("STEP 3: reviewing a batch of {} service updates since {}".format(len(items), oldest_update.strftime(NORMALIZED_DATE_FORMAT)))

                        for item in items:
                            # Skip everything that's not categorized.
                            rip = (item["instance"]["S"].split(":"))[0]
                            if rip not in services:
                                no_cat += 1
                            else:
                                # Service-specific row.
                                if "belongs_to_instance" not in item:
                                    services[rip]["instances"][item["version_instance"]["N"]] = item
                                    service_specific += 1
                                else:
                                    # Service-in-region row.
                                    region = item["belongs_to_instance"]["S"]
                                    if region not in notifications:
                                        unconfig_region += 1
                                        if region not in unconfig_regions:
                                            unconfig_regions.append(region)
                                            logger.warn("no NOTIFICATION configured for region {}".format(item["belongs_to_instance"]["S"]))
                                            logger.warn("EXAMPLE of WEIRD instance: {}".format(item))
                                    else:
                                        possibly_relevant += 1
                                        logger.info("adding history for {} in {}".format(rip, region))
                                        if region not in services[rip]["regions"]:
                                            logger.info("adding history for {} in {}".format(rip, region))
                                            services[rip]["regions"][region] = dict(
                                                history={0: item},
                                                notification=notifications[region]
                                            )
                                        else:
                                            services[rip]["regions"][region]["history"][int(item["version_instance"]["N"])] = item

                    if "LastEvaluatedKey" in response:
                        args["ExclusiveStartKey"] = response["LastEvaluatedKey"]
                    else:
                        break

                logger.info("SKIPPED UPDATES: {} were for services that are not categorized, {} were for regions for which we are not configured to send updates, {} were service-specific (non-regional) updates".format(no_cat, unconfig_region, service_specific))
                logger.info("{} updates are possibly relevant".format(possibly_relevant))

                # Now we're ready to start matching up the service information we have with the messages that need sending.
                messages = {}
                for service_key in services:
                    service = services[service_key]
                    for region_key in service["regions"]:

                        # # # # HACK # # # #
                        # remove_system_updates(service, region_key)
                        # # # # HACK # # # #

                        service_in_region = service["regions"][region_key]
                        if (region_key in notifications) and ("history" in service_in_region) and (len(service_in_region["history"]) > 0):
                            notification = notifications[region_key]
                            if 'updated' in service_in_region["history"][0] and 'S' in service_in_region["history"][0]['updated']:
                                region_updated_date = parser.parse(service_in_region["history"][0]["updated"]["S"]).replace(tzinfo=pytz.UTC)
                                # logger.info("STEP 4 (loop): compare dates: {} last updated on {}, region {} last notification was {}".format(service_key, region_updated_date, region_key, notification["updated"]))
                                if region_updated_date >= notification["updated"]:
                                    logger.info("STEP 4.a: TRIGGERED {} in {} last updated on {}, last notification sent on {}".format(service_key, region_key, region_updated_date, notification["updated"]))

                                    previous_dates = []
                                    try:
                                        response = ddb.query(
                                            TableName=table,
                                            KeyConditions={
                                                "artifact": {"ComparisonOperator": "EQ", "AttributeValueList": [{"S": "SERVICE"}]},
                                                "instance": {"ComparisonOperator": "BEGINS_WITH", "AttributeValueList": [{"S": service_key}]}
                                            },
                                            QueryFilter={
                                                "belongs_to_instance": {"ComparisonOperator": "EQ", "AttributeValueList": [{"S": region_key}]}
                                            }
                                        )

                                        if "Items" not in response.keys():
                                            logger.info("no service history items.  wtf.")
                                        else:
                                            items = response["Items"]
                                            logger.info("STEP 4.a.1: {} service history in {} response contains {} items".format(service_key, region_key, len(items)))

                                            for item in items:
                                                index = int(item["version_instance"]["N"])
                                                service_in_region["history"][index] = item

                                            # # # # HACK # # # #
                                            # remove_system_updates(service, region_key)
                                            # # # # HACK # # # #

                                            history = service_in_region["history"]
                                            logger.info("{} in {} has {} versions".format(service_key, region_key, len(history)))
                                            logger.info("most recent instance is: {}".format(history[0]))

                                            new_confidence = "({})".format(get_confidence(history[0]))

                                            new_date = "See Note"
                                            if "date" in history[0]:
                                                new_date = condense_date_text(history[0]["date"]["S"])
                                            else:
                                                if "updated" in history[0]:
                                                    new_date = condense_date_text(history[0]["updated"]["S"])
                                                else:
                                                    # Give up. Uncertain how to report on this if we don't know when it happened.
                                                    logger.error("NO UPDATED DATE: {}".format(history))
                                                    break

                                            # The bare minimum requirements to generate an email are a change to date, confidence, note, or status.
                                            # Most specifically, this will exclude changes to only the category since those aren't noted in the email
                                            # (an email based soley on a category change would, confusingly, contain no changed information).
                                            # See https://sim.amazon.com/issues/RECON-4560.

                                            if not has_relevant_changes(history):
                                                # To determine if we are accurately determine which services were updated
                                                logger.warn(f"IGNORING update with no relevant changes to date, note, or confidence and no status change to GA: {history}")
                                                break

                                            if "updater" in history[0]:
                                                if ((history[0]["updater"]["S"] == "system") or (history[0]["updater"]["S"] == "RIPScorecardListener")):
                                                    logger.warn("IGNORING SYSTEM UPDATE: {}".format(history[0]))

                                            # Sometimes we get system updates for things in the past. I don't know why. Sure, I'd like to know.
                                            # But figuring things like that out take time and I have to finish this report RIGHT NOW. Maybe
                                            # there will be time in the future to look into this.
                                            #
                                            # So, let's not send mail about past updates so we don't get questions about it from users.
                                            if ("date" in history[0]) and ("updated" in history[0]):
                                                difference = (parser.parse(history[0]["updated"]["S"]).replace(tzinfo=pytz.UTC) - parser.parse(history[0]["date"]["S"]).replace(tzinfo=pytz.UTC)).days
                                                logger.warn("POTENTIAL OLD event for {} in {}, difference: {}".format(service_key, region_key, difference))
                                                if difference > PAST_SYSTEM_EVENT_THRESHOLD:
                                                    logger.error("IGNORING an update about a past event for {} in {} {} days ago: {}".format(service_key, region_key, difference, history))
                                                    break

                                            updater = ""
                                            if "updater" in history[0]:
                                                updater = history[0]["updater"]["S"]

                                            note = ""
                                            if "note" in history[0]:
                                                note = history[0]["note"]["S"]

                                            if ("date" not in history[0]) and ("confidence" not in history[0]):
                                                if ("status" not in history[0]) or (len(history[0]["status"]["S"]) == 0):
                                                    # This is another case where we have nothing to report if there's no date, status, or confidence change.
                                                    # Just abort.
                                                    logger.error("IGNORING an update with no date, status, or confidence change for {} in {}: {}".format(service_key, region_key, history))
                                                    break
                                                if (("status" in history[0]) and (history[0]["status"]["S"] == "GA")):
                                                    # Only send these on GA/Complete. Otherwise, we send redundant updates about build status changes which RMS
                                                    # (presumably) is already sending.
                                                    pass
                                                else:
                                                    break

                                            # De-dupe.
                                            i = 1
                                            previous_dates = []
                                            end = len(history) - 1
                                            tup = ( ("date", new_date), ("confidence", new_confidence) )
                                            seen = set()
                                            seen.add(tup)
                                            while i < end:
                                                previous = {}
                                                if "date" in history[i]:
                                                    previous = {"date": condense_date_text(history[i]["date"]["S"]), "confidence": ""}
                                                    if "confidence" in history[i]:
                                                        previous["confidence"] = "(" + history[i]["confidence"]["S"] + ")"
                                                    tup = ( ("date", previous["date"]), ("confidence", previous["confidence"]) )

                                                    logger.warn("TUP COMPARE: look for '{}' in '{}'".format(tup, seen))

                                                    if tup not in seen:
                                                        seen.add(tup)
                                                        previous_dates.append(previous)
                                                i += 1

                                            # Sort.
                                            previous_dates = sorted(previous_dates, key=lambda item: item["date"], reverse=True)

                                            # Add visual separators.
                                            i = 0
                                            end = len(previous_dates)
                                            while i < end:
                                                separator = ""
                                                if i + 1 < end:
                                                    separator = ","
                                                previous_dates[i]["separator"] = separator
                                                i += 1

                                            name = get_service_name(service["instances"]["0"])

                                            if region_key not in messages:
                                                messages[region_key] = {"services": []}

                                            if (updater == "") and (note == ""):
                                                note = "automated update"

                                            messages[region_key]["services"].append(dict(
                                                rip=service_key,
                                                service_name=name,
                                                new_date=new_date,
                                                new_confidence=new_confidence,
                                                previous=previous_dates,
                                                note=note,
                                                changed_on_date=region_updated_date.strftime(NORMALIZED_DATE_FORMAT),
                                                actor_username=updater if updater != "system" else ""
                                            ))
                                            messages[region_key]["last_sent_date"] = notification["updated"].strftime(NORMALIZED_DATE_FORMAT)
                                            messages[region_key]["airport_code"] = notification["region"]

                                    except Exception as e:
                                        logger.error("unable to fetch history in region for {} because {}\n{}".format(service_key, repr(e), format_exc()))
                                else:
                                    pass
                                    # logger.info("STEP 4.b: we've already sent mail about {} in {}".format(service_key, notification["region"]))

                logger.info("STEP 5: preparing to send {} messages".format(len(messages)))
                for message_key in messages.keys():
                    service_list = sorted(messages[message_key]["services"], key=lambda item: item["service_name"])

                    params = {
                        "message_group_name": notifications[message_key]["instance"],
                        "params": json.dumps({
                            "last_sent_date": messages[message_key]["last_sent_date"],
                            "airport_code": messages[message_key]["airport_code"],
                            "services": service_list
                        })
                    }

                    try:
                        logger.info("sending message to {} stage with payload: {} ".format(MM_STAGE, params))
                        mm_helper = MessageMultiplexerHelper(endpoint=get_mm_endpoint(MM_STAGE), own_account_number=os.environ["ACCOUNT_ID"])
                        response = mm_helper.perform_operation(operation="send_message", params=params, convert_message_group_name=True)

                        logger.info("sent mail! {}".format(response))
                        metrics = increment_metric(metrics, "message_send_success")

                        try:
                            params = dict(
                                TableName=table,
                                Key={
                                    "artifact": {"S": "NOTIFICATION"},
                                    "instance": {"S": notifications[message_key]["instance"]}
                                },
                                AttributeUpdates={
                                    "updated": {
                                        "Action": "PUT",
                                        "Value": {"S": now.strftime(NORMALIZED_DATE_FORMAT_WITH_SEC)}
                                    }
                                })
                            response = ddb.update_item(**params)
                            logger.info("STEP 5: successfully updated NOTIFICATION entry with {}: {}".format(params, response))

                        except Exception as e:
                            logger.error("unable to update notifications with '{}' because {} \n{}".format(params, repr(e), format_exc()))

                    except Exception as e:
                        logger.error("unable to send message: {}, because {} \n{}".format(params, repr(e), format_exc()))
                        metrics = increment_metric(metrics, "message_send_failure")

            except Exception as e:
                logger.error("unable to query for updates: {} \n{}".format(repr(e), format_exc()))

        except Exception as e:
            logger.error("unable to get list of categorized services: {} \n{}, bozo".format(repr(e), format_exc()))

    except Exception as e:
        logger.error("unable to read in notifications: {} \n{}".format(repr(e), format_exc()))

    submit_cloudwatch_metrics(metrics_dict=metrics, service_name=context.function_name)
