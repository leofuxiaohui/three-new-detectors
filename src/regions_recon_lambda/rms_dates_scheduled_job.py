import simplejson as json
import boto3
import requests

import urllib.parse
from datetime import datetime
from boto3.dynamodb.conditions import Key, Attr

from aws_requests_auth.aws_auth import AWSRequestsAuth
from regions_recon_python_common.buildables_dao_models.service_plan import ServicePlan

from regions_recon_lambda.utils.rms_dates_helpers import days_between, get_short_date, valid_date, validate_service_name, validate_airport_code, validate_rms_milestone

from regions_recon_python_common.utils.log import get_logger
from regions_recon_python_common.utils.cloudwatch_metrics_utils import submit_cloudwatch_metrics, increment_metric
from regions_recon_python_common.utils.misc import get_all_ddb_results
from regions_recon_lambda.utils.constants import RIP_FEATURE_PREFIX, RIP_SERVICE_PREFIX, RIP_SERVICE_STATUS_INDEX, RIP_FEATURE_STATUS_INDEX, AWS_RMS_ANALYTICS

logger = get_logger()
metrics = {}


def get_status_from_rip_arn(arn):
    logger.info(arn)
    if RIP_FEATURE_PREFIX in arn:
        return arn[len(RIP_FEATURE_PREFIX):].split("/")[RIP_FEATURE_STATUS_INDEX]
    return arn[len(RIP_SERVICE_PREFIX):].split("/")[RIP_SERVICE_STATUS_INDEX]


def get_service_dates_query_params(plan, region):
    return {
        "IndexName": "artifact-plan-index",
        "ConsistentRead": False,
        "KeyConditionExpression": Key("artifact").eq("SERVICE") & Key("plan").eq(plan),
        "FilterExpression": Attr("version_instance").eq(0) & Attr("belongs_to_instance").eq(region.upper()) & Attr("status").ne("GA")
    }


def get_GE_service_dates_from_buildables_for_region(table, region):
    lb_services_params = get_service_dates_query_params("Globally Expanding - Launch Blocking", region)
    mandatory_services_params = get_service_dates_query_params("Globally Expanding - Mandatory", region)

    all_services = get_all_ddb_results(table, lb_services_params) + get_all_ddb_results(table, mandatory_services_params)
    logger.info("Found {} mandatory services for region {}".format(len(all_services), region))

    return all_services


def get_rms_and_recon_combined_object(all_milestones, service):
    global metrics
    service_name = service["instance"].split(":")[0]
    service_region = service["instance"].split(":")[2]

    # gets and trims time off launch date YYYY-MM-DD
    service_launch_date_long = service.get("date", "-")
    service_launch_date = get_short_date(service_launch_date_long)


    # iterate over all milestones returned by rms to find the one we care about.. GA
    found_matching_milestone = False
    for milestone in all_milestones:

        # make sure the data is as expected before we start reaching into it.
        if (validate_rms_milestone(milestone, logger)):
            namespace_milestone = milestone["namespace"]

            # checks if namespace for this milestone matches
            # * GA milestone specific namespace format
            # * Service name matches
            # * Service region matches
            GA_matched_namespace = f"instance/service/{service_name}/{service_region}/GA" in namespace_milestone

            if GA_matched_namespace:
                # logger.info(json.dumps(milestone, indent=2))

                milestone_status = milestone["status"]
                if milestone_status == "COMPLETED":
                    rms_date = "COMPLETED"
                    slack = None
                else:
                    early_finish = milestone["early_finish"] # one we care about
                    late_finish = milestone["late_finish"] # might care about range
                    slack = milestone["slack"]
                    rms_date = get_short_date(early_finish)


                if (valid_date(service_launch_date) and valid_date(rms_date)):
                    date_diff = days_between(service_launch_date, rms_date)
                else:
                    date_diff = None

                found_matching_milestone = True

                return {
                    "service": service_name,
                    "region": service_region,
                    "service_launch_date": service_launch_date,
                    "rms_early_finish_date": rms_date,
                    "slack": slack,
                    "date_diff": date_diff
                }


    if found_matching_milestone is False:
        logger.error("Was not able to find GA milestone for service: {} in region: {}".format(service_name, service_region))
        metrics = increment_metric(metrics, "no_ga_milestone_found")


def call_rms_and_create_diff_object(auth, service):
    global metrics

    service_name = service["instance"].split(":")[0]
    service_region = service["instance"].split(":")[2]
    if (validate_service_name(service_name, logger) and validate_airport_code(service_region, logger)):
        service_name = service_name.replace("/", "+")
        encoded_service_name = urllib.parse.quote(service_name)
        encoded_service_region = urllib.parse.quote(service_region)

        logger.debug("calling rms for data for {} in {}".format(service_name, service_region))

        url = "https://{}/dates?region={}&service={}".format(AWS_RMS_ANALYTICS, encoded_service_region, encoded_service_name)
        response = requests.get(url, auth=auth)

        data = response.content
        json_object = json.loads(data)

        all_milestones = json_object.get("dates", None)
        if (all_milestones is not None):
            return get_rms_and_recon_combined_object(all_milestones, service)
        else:
            logger.error("RMS Response did not come back as expected for service {} in region {}".format(service_name, service_region))
            ### Sometimes you will get this error if you are not allowlisted - to do so
            # Cut a ticket to "AWS / Regions Management Service / Contact Us"
            # Title: "[Analytics] Dates Allowlisting Request"
            # Include your use case, and accounts/roles/users to allowlist

            metrics = increment_metric(metrics, "rms_response_invalid")
    else:
        logger.error("There was an issue validating the service coming back from Recon: {} , {}".format(service_name, service_region))


def find_service_and_update_dynamo(data, all_services_plans):
    global metrics

    composedData = "{}:v0:{}".format(data["service"], data["region"])
    found = False

    # find the ddb data that matches this piece of data
    for service in all_services_plans:
        service_instance = service["instance"]

        if service_instance == composedData:
            found = True
            if service.get("rms_early_finish_date") == data["rms_early_finish_date"]:
                logger.debug("🏃‍♂️ No need to write. No data changed for service {} in region {}, date: {}".format(data["service"], data["region"], data["rms_early_finish_date"]))
                metrics = increment_metric(metrics, "ddb_item_already_uptodate")
            else:
                original_date = service.get("rms_early_finish_date", "non-existent")
                logger.info("✅ Found new date value from RMS for service {} in region {}, writing to DB. Was {}, is now {}"
                    .format(data["service"], data["region"], original_date, data["rms_early_finish_date"]))

                plan = ServicePlan.create_and_backfill(
                    artifact="SERVICE",
                    instance=service_instance,
                    rms_early_finish_date=data["rms_early_finish_date"],
                    rms_early_finish_date_updated=datetime.now().isoformat(),
                )

                plan.save()

                logger.debug(f"UPDATED: {plan}")
                metrics = increment_metric(metrics, "ddb_updated_item")

            break

    return found


# Entry point for lambda - scheduled job every 6 hours
def pull_and_write_rms_dates(event, context):
    # do NOT remove these lines!  having the full event is required for analysis (appsec requirement)
    logger.debug("event: {}".format(event))
    logger.debug("context: {}".format(context.__dict__))

    logger.info("START, good luck bozo")
    regions_to_pull_dates = {"ale", "apa", "bpm", "cgk", "cpt",
                             "dxb", "hyd", "kix", "ltw", "mel",
                             "mxp", "tlv", "zaz", "zrh"}


    # Step 1 - Get Mandatory Services plans for regions we care about from buildables table
    logger.info("Starting scan of buildables table to get list of services")

    table_name = "buildables"
    ddb_resource = boto3.resource("dynamodb", region_name="us-east-1")
    table = ddb_resource.Table(table_name)

    all_services_plans = []
    for region in regions_to_pull_dates:
        all_services_plans += get_GE_service_dates_from_buildables_for_region(table, region)



    # Step 2 - Reach out to RMS to get date info
    logger.info("Starting api calls out to RMS Analytics to get dates")
    session = boto3.Session()
    credentials = session.get_credentials()
    # Credentials are refreshable, so accessing your access key / secret key
    # separately can lead to a race condition. Use this to get an actual matched set.
    current_credentials = credentials.get_frozen_credentials()
    auth = AWSRequestsAuth(
        aws_access_key=current_credentials.access_key,
        aws_secret_access_key=current_credentials.secret_key,
        aws_token=current_credentials.token,
        aws_host=AWS_RMS_ANALYTICS,
        aws_region="us-east-1",
        aws_service="execute-api"
    )

    found_data = []
    for service in all_services_plans:
        rms_result = call_rms_and_create_diff_object(auth, service)
        if rms_result is not None:
            found_data.append(rms_result)

    logger.info("Got {} items from RMS".format(len(found_data)))



    # Step 3 - Update the database in buildables with the new service in region rms_date value - But dont let it increment version
    found_service_and_updated = False

    for data in found_data:
        # Example data object - intermediate store for rms + recon data
        # {
        #     "service": "ACMPrivateCA",
        #     "region": "CPT",
        #     "service_launch_date": "2020-05-29",
        #     "rms_early_finish_date": "2020-05-07",
        #     "slack": null,
        #     "date_diff": -22
        # }
        found_service_and_updated = find_service_and_update_dynamo(data, all_services_plans)

        if not found_service_and_updated:
            logger.error("😭 Something went wrong, could not find")


    submit_cloudwatch_metrics(metrics_dict=metrics, service_name="RMSDatesScheduledJobFunction")
    logger.info(json.dumps(metrics, indent=2))
    logger.info("DONE, good job bozo")
    return "Success!"
