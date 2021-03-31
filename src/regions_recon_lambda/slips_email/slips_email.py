import os
import pprint
import logging
import json
from datetime import datetime, timezone, timedelta
from boto3.dynamodb.conditions import Key, Attr
from dateutil import parser
import pytz
from regions_recon_python_common.utils.cloudwatch_metrics_utils import submit_cloudwatch_metrics, increment_metric
from regions_recon_python_common.message_multiplexer_helper import MessageMultiplexerHelper, get_mm_endpoint
from regions_recon_python_common.utils.constants import BUILDABLES_TABLE_NAME
from regions_recon_python_common.utils.log import get_logger
from regions_recon_python_common.utils.misc import get_rip_name_from_instance_field
from regions_recon_lambda.utils.dynamo_query import DynamoQuery
from regions_recon_lambda.slips_email.slips_email_dao import SlipsEmailDAO


MESSAGE_GROUP_NAME = "region-slips"
CONDENSED_DATE_FORMAT = "%Y-%m-%d"
SLIP_DELTA = 30
NORMALIZED_DATE_FORMAT = "%Y-%m-%d %H:%M %Z"

logger = get_logger(logging.INFO)
mmlogger = logging.getLogger('messagemultiplexer')
mmlogger.setLevel(logging.WARN)


def send_slips_mail(event, context):
    try:
        if 'debug' in event:
            logger.setLevel(logging.DEBUG)
        if 'debug' in event or 'logmm' in event:
            mmlogger.setLevel(logging.INFO)
        dryrun = 'dryrun' in event

        metrics = {}
        metrics["message_send_success"] = 0
        metrics["message_send_failure"] = 0

        dao = SlipsEmailDAO()

        results = send_slips_mail_internal(dao, dryrun, metrics)
        metrics = increment_metric(metrics, "message_send_success")
        return results

    except:
        logger.exception("Lambda function failed.")
        metrics = increment_metric(metrics, "message_send_failure")
        raise

    finally:
        if dryrun:
            logger.info("CloudWatch metrics (not sent because dryrun): {}".format(metrics))
        else:
            submit_cloudwatch_metrics(metrics_dict=metrics, service_name='ServiceSlipsMailer')



def send_slips_mail_internal(dao, dryrun, metrics):
    """
    Check out the README.md in this folder.  It has details on this function and the whole folder too.
    """
    # Basic 'global' values we'll use a lot

    now = datetime.now(timezone.utc)
    time_horizon = int(os.environ.get("TIME_HORIZON", "336"))  # 14 days * 24 hours/day = 336
    update_limit = now - timedelta(hours=time_horizon)
    logger.info ("INPUTS: now={}, time_horizon={}h ({}d), update_limit={}".format(now, time_horizon, time_horizon/24, update_limit))

    # Gather data from the database

    updated_cutoff = dao.get_update_cutoff(update_limit)
    logger.info("Reporting on slips since {}".format(date2str(updated_cutoff)))

    unlaunched_regions = dao.get_unlaunched_regions()
    logger.info("Unlaunched regions: {}".format(unlaunched_regions))

    service_items, plan_items = dao.get_services_and_plans()

    # Business Logic

    plan_items = remove_unlaunched_regions(plan_items, unlaunched_regions)

    services = build_services(service_items, plan_items)

    all_regions = gather_unique_regions(plan_items)

    logger.info("{} SERVICES: {}".format(len(services), sorted(services.keys())))
    logger.info("{} REGIONS: {}".format(len(all_regions), all_regions))


    populate_previous_plans(dao, services, all_regions, updated_cutoff)
    populate_noplan(services, all_regions)
    populate_has_notes(services, all_regions)

    slips, improvements = create_slips_improvements(services, all_regions)
    metrics['slips_count'] = len(slips)
    metrics['improvements_count'] = len(improvements)
    log_services(services)

    logger.info("Found {} slips and {} improvements".format(len(slips), len(improvements)))
    readable_slips = [ "{}:{} = {} days".format(s['name_rip'], s['region'], s['change']) for s in slips ]
    readable_improvements = [ "{}:{} = {} days".format(i['name_rip'], i['region'], i['change']) for i in improvements ]

    logger.info("SLIPS: {}".format(", ".join(readable_slips)))
    logger.info("IMPROVEMENTS: {}".format(", ".join(readable_improvements)))

    unplanned_regions = gather_unplanned_regions(services)
    logger.debug("Unplanned regions {}".format(unplanned_regions))

    mm_params = create_mm_params(updated_cutoff, slips, improvements, unplanned_regions)
    logger.debug("Final params to MessageMultiplexer:\n%s",
        pprint.pformat(mm_params, indent=4, width=150))

    if not dryrun:
        send_to_messagemultiplexer(mm_params)
        dao.set_update_cutoff()
    else:
        logger.info("DRYRUN, nothing sent to Message Multiplexer, high-water-mark in DDB not updated")

    return mm_params



def remove_unlaunched_regions(plan_items, unlaunched_regions):
    """
    Strip out all entries that have belongs_to_instance value that is in unlaunched_regions.
    Put another way, { 'belongs_to_instance': 'ABC' } will be in the output if
    unlaunched_regions is [ 'ABC', 'DEF' ] and won't be in the output if unlaunched_regions
    is [ 'GHI', 'JKL' ].
    """
    return [ plan  for plan in plan_items  if plan.get('belongs_to_instance') not in unlaunched_regions ]


def build_services(service_items, plan_items):
    services = {}

    # Pass 1: build the keys in services
    for service in service_items:
        rip_name = get_rip_name_from_instance_field(service['instance'])
        services[rip_name] = dict(
            # Raw items about each region for which we have data about this service.
            regions={},

            # Raw items about this service's non-regional data.
            metadata={
                str(service['version_instance']): service
            },

            # List of regions where this service lacks build plans.
            noplan=[],

            # In many cases, their are no notes (yet) for unplanned regions so it
            # makes the most sense to display only the list of regions.
            # If, however, there are notes for even one region in the noplan list,
            # we use a more detailed display so we can show said note(s).
            has_notes=False
        )

    # Important note!  There are services that don't have a plan that also have corresponding service
    # instances that DO have a plan.  Hopefully this is just bad data, but can also be because of a
    # deprecated service (I think...).   SO, there's an important side-effect in this function: no
    # service instance in plan_items can get into the return value "services" if it's service in
    # service_items doesn't have a plan.  This is because the service_items were retrieved above from
    # the database index artifact-plan-index.

    # Pass 2: Populate 'regions' in each service
    for plan in plan_items:
        rip_name = get_rip_name_from_instance_field(plan['instance'])
        if rip_name in services:
            region = plan.get('belongs_to_instance')
            if region not in services[rip_name]['regions']:
                services[rip_name]['regions'][region] = {}
            services[rip_name]['regions'][region][str(plan['version_instance'])] = plan

    return services


def gather_unique_regions(plan_items):
    all_regions = []
    for plan in plan_items:
        region = plan.get('belongs_to_instance')
        if region not in all_regions:
            all_regions.append(region)
    all_regions.sort()
    return all_regions


def find_lowest_version_added(updates):
    lowest_num_not_zero = 9999 # in python 3 there is no max int
    found_lowest = False
    for current_item in updates.keys():
        if (int(current_item) < lowest_num_not_zero and int(current_item) != 0):
            lowest_num_not_zero = int(current_item)
            found_lowest = True

    if found_lowest:
        return lowest_num_not_zero
    else:
        return None


def add_updates_based_on_cutoff(dao, updates, service_key, region_key, cutoff):
    zero_instance = f"{service_key}:v0:{region_key}"
    highest_version = none_safe_get(updates, ["0", "version_latest"])
    logger.debug(f"highest update version is: {highest_version}")
    current_version = highest_version

    while current_version > 0:
        # check to see if it should be added
        item = dao.get_plan(service_key, current_version, region_key)
        current_item_updated_date = none_safe_get(item, ["updated"])
        current_updated_date_str = date2str(current_item_updated_date)

        # if we have found an item with updated attr and its within the cutoff
        if current_item_updated_date is not None and current_item_updated_date >= cutoff:
            updates[str(current_version)] = item
            logger.debug(f"{zero_instance} -- {current_updated_date_str} >= cut-off ({cutoff}): Grabbed previous version {current_version} !!")
        else:
            logger.debug(f"{zero_instance} -- {current_updated_date_str} != cut-off ({cutoff}) or {current_version} not found!  (ignored)")
            # not worth checking past items since this version isnt within cutoff - exit loop
            current_version = 0

        current_version = current_version - 1


def populate_previous_plans(dao, services, all_regions, cutoff):
    for service_key, service in services.items():
        logger.debug(f"Collecting data for service {service_key}")
        for region_key in all_regions:
            zero_instance = "{}:v0:{}".format(service_key, region_key)
            if region_key in service["regions"]:
                updates = service["regions"][region_key] # This is the global object where all relevent data found is applied
                logger.debug(f"Here is updates object before application: {updates}")

                add_updates_based_on_cutoff(dao, updates, service_key, region_key, cutoff)

                logger.debug(f"Updates object gathered after innitial time window calculations: {updates}")

                # Add the version before the range for date calculations
                found_lowest = find_lowest_version_added(updates)
                if found_lowest is not None:
                    logger.debug(f"Found lowest version_instance: {found_lowest} - adding version before it for math")
                    one_lower = found_lowest - 1
                    item = dao.get_plan(service_key, one_lower, region_key)
                    updates[str(one_lower)] = item
                else:
                    # was not able to find a version thats not zero - this means there is only version zero
                    # lets add its cooresponding version_latest for math
                    highest_version = none_safe_get(updates, ["0", "version_latest"])
                    logger.debug(f"Did not find any revisions - adding highest version: {highest_version}")
                    item = dao.get_plan(service_key, highest_version, region_key)
                    updates[str(highest_version)] = item

                logger.debug(f"Updates object gathered after all modifications: {updates}")


def populate_noplan(services, all_regions):
    def mark_region_planned(svcbin, region):
        try:
            svcbin["noplan"].remove(region)
        except ValueError as e:
            pass

    for svcbin_key, svcbin in services.items():
        # Start with the assumption that all regions are unplanned and remove them from this list as we find plans.
        svcbin["noplan"] = all_regions.copy()

        for region_key in all_regions:
            updates = none_safe_get(svcbin, ["regions", region_key], [])
            if len(updates) > 0:
                status = none_safe_get(updates, ["0", "status"])
                confidence = none_safe_get(updates, ["0", "confidence"])
                has_date = "date" in updates["0"]
                if status == "GA" or status == "IA" or confidence == "Complete" or has_date:
                    mark_region_planned(svcbin, region_key)


def populate_has_notes(svcbins, all_regions):
    """
    For each svcbin, set has_notes to true if any instances don't have a plan and do have a note.
    """
    for svcbin_key, svcbin in svcbins.items():
        for region_key in all_regions:
            region = none_safe_get(svcbin, ["regions", region_key], [])
            if len(region) > 0:
                if region_key in svcbin["noplan"] and "note" in region["0"] and len(region["0"]["note"]):
                    svcbin["has_notes"] = True


def create_change_object(updates, service_data, service_name, region_key, previous_date, current_date, delta):
    note = ""
    if "note" in updates["0"]:
        note = updates["0"]["note"]
    updated = none_safe_get(updates, ['0', 'updated'])

    if updated is not None:
        updated = updated.strftime(CONDENSED_DATE_FORMAT)

    updater = none_safe_get(updates, ['0', 'updater'], '')
    if updater == "system":
        updater = ''

    change = {
        "updated": updated,
        "updater": updater,
        "name_pretty": none_safe_get(service_data, ['metadata', '0', 'name_pretty']),
        "name_rip": service_name,
        "region": region_key,
        "previous": previous_date.strftime(CONDENSED_DATE_FORMAT),
        "current": current_date.strftime(CONDENSED_DATE_FORMAT),
        "change": abs(delta),
        "note": note
    }

    return change


def generate_slips_and_improvements(service_name, service_data, region_key, updates):
    logger.debug(f"Calculating slips or improvements for serivce '{service_name}' in region '{region_key}'")
    slips = []
    improvements = []

    if "date" in updates["0"]:
        current_date = updates["0"]["date"]
        prev_index = str(find_lowest_version_added(updates))
        logger.debug(f"found prev index: {prev_index}")

        if prev_index not in updates or "date" not in updates[prev_index]:
            logger.debug(f"No previous date for {service_name} in {region_key} - calculations cant be done")
        else:
            previous_date = updates[prev_index]["date"]
            delta = (current_date - previous_date).days

            if abs(delta) >= SLIP_DELTA:
                change = create_change_object(updates, service_data, service_name, region_key, previous_date, current_date, delta)

                if delta > 0:
                    slips.append(change)
                    logger.debug("{} in {}: slip (delta of {}d >= {}d)".format(service_name, region_key, delta, SLIP_DELTA))
                else:
                    improvements.append(change)
                    logger.debug("{} in {}: improvement (delta of {}d <= -{}d)".format(service_name, region_key, delta, SLIP_DELTA))

            else:
                logger.debug("{} in {} -- delta of {}d < {}d, so no slip or improvement.".format(service_name, region_key, abs(delta), SLIP_DELTA))

    else:
        logger.debug(f"Missing date for {service_name}:v0:{region_key} - calculations cant be done")


    return (slips, improvements)


def create_slips_improvements(services, all_regions):
    slips = []
    improvements = []
    logger.debug("Slips and Improvements:")
    for service_name, service_data in services.items():
        for region_key in all_regions:
            updates = none_safe_get(service_data, ["regions", region_key], [])
            if len(updates) > 1:
                per_service_slips, per_service_improvements = generate_slips_and_improvements(service_name, service_data, region_key, updates)

                slips = slips + per_service_slips
                improvements = improvements + per_service_improvements

    return (slips, improvements)


def gather_unplanned_regions(services):
    unplanned = []
    for svcbin_key, svcbin in services.items():
        # noplan_limit is mostly used for formatting (see below) and it also tells us if the list is empty
        noplan_limit = len(svcbin["noplan"]) - 1
        if noplan_limit >= 0:
            noplan_list = sorted(svcbin["noplan"])
            noplan = {
                "has_notes": svcbin["has_notes"],
                "name_pretty": none_safe_get(svcbin, ['metadata', '0', 'name_pretty']),
                "name_rip": svcbin_key
            }
            noplan_regions = []
            if svcbin["has_notes"]:
                noplan_regions = []
                for i in noplan_list:
                    updated = none_safe_get(svcbin, ['regions', i, '0', 'updated'])
                    if updated:
                        updated = updated.strftime(CONDENSED_DATE_FORMAT)
                    updater = none_safe_get(svcbin, ["regions", i, '0', 'updater'])
                    if updater == 'system':
                        updater = ''
                    noplan_regions.append({
                        "region": i,
                        "note": none_safe_get(svcbin, ["regions", i, "0", "note"]),
                        "updated": updated,
                        "updater": updater
                    })
            else:
                noplan_regions = [{"region": i, "separator": "," if noplan_list.index(i) < noplan_limit else ""} for i in noplan_list]
            noplan["regions"] = noplan_regions
            unplanned.append(noplan)

    unplanned = sorted(unplanned, key=lambda item: item["name_pretty"])
    return unplanned


def create_mm_params(updated, slips, improvements, unplanned):
    unplanned = sorted(unplanned, key=lambda item: item.get("name_pretty"))
    return {
        "beginning": updated.strftime(CONDENSED_DATE_FORMAT),
        "end": datetime.now(timezone.utc).strftime(CONDENSED_DATE_FORMAT),
        "last_sent_date": updated.strftime(NORMALIZED_DATE_FORMAT),
        "slip_delta": SLIP_DELTA,
        "slips_exist": len(slips) > 0,
        "slip_count": len(slips),
        "slips": slips,
        "improvements_exist": len(improvements) > 0,
        "improvement_count": len(improvements),
        "improvements": improvements,
        "unplanned_count": len(unplanned),
        "unplanned": unplanned
    }


def send_to_messagemultiplexer(params):
    mm_stage = os.environ['MM_STAGE']
    acct_num = os.environ['ACCOUNT_ID']

    mm_arg = {
        "message_group_name": MESSAGE_GROUP_NAME,
        "params": json.dumps(params)
    }
    mm_helper = MessageMultiplexerHelper(endpoint=get_mm_endpoint(mm_stage), own_account_number=acct_num)
    response = mm_helper.perform_operation(operation="send_message", params=mm_arg, convert_message_group_name=True)
    logger.info("sent mail! {}".format(response))


def log_services(services):
    if logger.isEnabledFor(logging.DEBUG):
        msg = []
        msg.append("Services:")
        for svcbin_key in sorted(services.keys()):
            msg.append("    {}:".format(svcbin_key))
            for region_key in sorted(services[svcbin_key]['regions'].keys()):
                region = services[svcbin_key]['regions'][region_key]
                log_region(region_key, region, msg)
            if len(services[svcbin_key]['regions'].keys()) == 0:
                msg.append("        (no regions)")
            msg.append("        noplan: {}".format(", ".join(services[svcbin_key]['noplan'])))
        logger.debug("\n".join(msg))


def log_region(region_key, region, msg):
    for version_num in sorted(region.keys()):
        updated = none_safe_get(region, [version_num, 'updated'])
        if updated:
            updated = updated.strftime('%Y-%m-%d')
        date = region[version_num].get('date')
        if date:
            date = date.strftime('%Y-%m-%d')
        msg.append("        {} v{}: updated={}  date={}".format(region_key, version_num, updated, date))


def date2str(dt):
    if dt is None:
        return "None"
    else:
        return dt.strftime("%Y-%m-%dT%H:%M")


def none_safe_get(root_object, attr_chain, default_value=None):
    """
    This replaces the abhorent chain of ugliness like this:
         if 'a' in obj and 'b' in obj['a'] and 'c' in obj['a']['b']:
    Pass the root object (which itself can be None!), and the list of indexes you want
    to go through.  It'll bail out and return default_value whenever it doesn't find
    one of the indexes.
    The above is replaced with none_safe_get(obj, ['a', 'b', 'c'])
    """
    if root_object is None or attr_chain is None or len(attr_chain) == 0:
        return default_value
    ret = root_object
    for attr in attr_chain:
        if attr in ret:
            ret = ret[attr]
        else:
            return default_value
    return ret
