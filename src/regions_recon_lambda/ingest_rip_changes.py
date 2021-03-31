import datetime
import os
import re
from typing import Optional

import boto3
from boto3.dynamodb.conditions import Key
from regions_recon_python_common.buildable_item import BuildableItem, BuildableService, BuildableRegion
from regions_recon_python_common.buildables_dao_models.region_metadata import RegionMetadata
from regions_recon_python_common.buildables_dao_models.service_metadata import ServiceMetadata
from regions_recon_python_common.buildables_dao_models.service_plan import ServicePlan
from regions_recon_python_common.buildables_ingestor import BuildablesIngestor
from regions_recon_python_common.utils.cloudwatch_metrics_utils import submit_cloudwatch_metrics, merge_metrics_dicts, \
    increment_metric, cloudwatch_timer
from regions_recon_python_common.utils.log import get_logger
from regions_recon_python_common.utils.misc import execute_retryable_call

from regions_recon_lambda.rip_ingestor.attributes_to_buildables_map import get_region_attributes_to_buildables_map, \
    get_service_attributes_to_buildables_map
from regions_recon_lambda.rip_ingestor.model_converters import convert_buildable_region_to_model, is_service_metadata, \
    convert_buildable_service_metadata_to_model, is_service_plan, convert_buildable_service_plan_to_model
from regions_recon_lambda.utils.dynamo_query import DynamoQuery
from .rip_message_record import RipMessageRecord

logger = get_logger()

SERVICES_TO_IGNORE_REGEX = "^(recon-integ)$|^(rms-integ-service|rms-canary-service)"

"""
Define what types of RIP messages to process.

See https://sim.amazon.com/issues/RIP-4697
"""
PROCESS_CHANGE_TYPES = (
    "DimensionChange",
    "DimensionInstanceChange",
    "ServiceStatusChange",
)

# This is hardcoded for now to fix sev2 - lets go back and replace this with some calls to rip
IGNORED_REGIONS = frozenset(("LUX", "SEA", "PEK", "KAT", "TST"))


def ingest_rip_changes(event, context):
    try:
        logger.debug("event: {}".format(event))
        logger.debug("context: {}".format(context.__dict__))

        ingestor = RipChangesIngestor(
            event=event,
            metrics_service_name=context.function_name,
        )
        ingestor.run_workflow()
    except:
        logger.exception("Uncaught exception.  Lambda will fail.  If this message came from SQS, check the DLQ.")
        raise


def is_in_list_of_ignored_services(service_name: str) -> bool:
    return bool(re.match(SERVICES_TO_IGNORE_REGEX, service_name))


def is_in_list_of_ignored_regions(region):
    return region in IGNORED_REGIONS


def parent_object_exists(parent_dimension_type, parent_dimension_name):
    db = DynamoQuery("buildables")
    response = db.query(
        key_condition=Key("artifact").eq(parent_dimension_type) & Key("instance").begins_with(parent_dimension_name + ":")
    )

    return bool(response)


def validate_region_item(buildable_item: BuildableItem) -> Optional[BuildableItem]:
    necessary_keys = {"status", "airport_code"}

    if not necessary_keys.issubset(set(buildable_item.local_item.keys())):
        logger.error(f"Invalid region item received from rip, the following item contains the rip update applied "
                     f"to the existing buildables record, {buildable_item}")
        return None

    valid_region_statuses = {"PLANNED", "BUILD", "IA", "GA"}
    buildable_item_status = buildable_item.local_item.get("status")

    if buildable_item_status not in valid_region_statuses:
        logger.error(f"The region item received from rip after a backfill update from Recon contains an illegal status"
                     f" of {buildable_item_status}")
        return None

    return buildable_item


class RipChangesIngestor(BuildablesIngestor):
    def __init__(self, metrics_service_name, event):
        self.sqs_client = None
        self.sqs_queue_url = os.environ["RIP_CHANGES_QUEUE_URL"]
        self.ddb_items_to_write = []
        self.region_items_to_write = []
        self.service_metadata_items_to_write = []
        self.service_plan_items_to_write = []
        self.metrics = {}
        self.metrics_service_name = metrics_service_name
        if 'Records' in event:
            self.records = [ RipMessageRecord(rec) for rec in event['Records'] ] # we're likely from SQS
        else:
            self.records = [ RipMessageRecord(event) ] # normalize to what SQS sends if we're called directly from Lambda, for example


    def run_workflow(self):
        logger.debug("Running workflow")

        logger.debug("Processing {} records".format(len(self.records)))
        for record in self.records:
            self.metrics = {}
            self.metrics["records_processed"] = 1

            if record.change_type in PROCESS_CHANGE_TYPES:
                logger.debug("message is {}".format(record.message))
                self.process_rip_message(message=record.message)
                self.write_to_dynamo()
            else:
                logger.debug("ignoring change type {}".format(record.change_type))
                self.metrics = increment_metric(self.metrics, "ignored_change_type")

            self.cleanup_sqs(record)
            submit_cloudwatch_metrics(metrics_dict=self.metrics, service_name=self.metrics_service_name)


    def process_rip_message(self, message):
        change_status = message["status"]
        logger.debug("change_status is {}".format(change_status))
        if change_status != "APPROVED":
            self.metrics = increment_metric(self.metrics, "change_not_approved")
            logger.info("Ignoring unapproved message: {}".format(message))
            return

        dimension_type = message["dimension"]["type"]
        if dimension_type == "SERVICE":
            buildable_item = self.get_buildable_service(message=message)
        elif dimension_type == "REGION":
            buildable_item = self.get_buildable_region(message=message)
        elif dimension_type == "TITAN":
            logger.info("Ignoring TITAN {}".format(message["dimension"]["name"]))
            return
        else:
            self.metrics = increment_metric(self.metrics, "unknown_dimension_type")
            logger.error("Unknown dimension type for message {}".format(message))
            return

        if buildable_item is None:
            return

        buildable_item.backfill_item_with_ddb_data()
        buildable_item.local_item.update(self.get_updating_agent_value())

        if dimension_type == "REGION":
            buildable_item = validate_region_item(buildable_item)

        self.metrics = merge_metrics_dicts(merge_to=self.metrics, merge_from=buildable_item.metrics)

        if dimension_type == "REGION":
            self.region_items_to_write.append(convert_buildable_region_to_model(buildable_item))

        elif is_service_metadata(buildable_item):
            self.service_metadata_items_to_write.append(convert_buildable_service_metadata_to_model(buildable_item))

        elif is_service_plan(buildable_item):
            self.service_plan_items_to_write.append(convert_buildable_service_plan_to_model(buildable_item))

        else:
            self.ddb_items_to_write += buildable_item.items_pending_write

    def get_buildable_region(self, message):
        """
        Process a message about a change to a RIP region.  Return a BuildableRegion item.
        Sample message - see region_non_ga.json
        """
        item_attrs = self.get_attributes_from_new_value(
            map_of_attr_names=get_region_attributes_to_buildables_map(),
            new_value=message["newValue"]
        )

        region_ac = message["dimension"]["name"]
        if is_in_list_of_ignored_regions(region_ac):
            logger.info(f"Ignoring REGION '{region_ac}' - its an ignored region (TEST/RETAIL/CLOSED)")
            return

        item_attrs["airport_code"] = region_ac
        item_attrs["name_sortable"] = region_ac
        item_attrs["updated"] = self.get_date_iso_string_from_epoch_milliseconds_timestamp(timestamp=message["approvedDate"])
        item_attrs["updater"] = message["registrant"]
        accessibility_attrs = message.get("newValue", {}).get("accessibilityAttributes")
        unwanted_attrs = ["TEST", "RETAIL", "CLOSING"]

        if accessibility_attrs is not None and any(item in unwanted_attrs for item in accessibility_attrs):
            logger.warning(f"Region is test, retail, or closing and is not tracked in the database. Accessibility attributes for region '{region_ac}' are '{accessibility_attrs}'")
            return None
        if "status" in item_attrs.keys() and item_attrs["status"] == "GA":
            date_from_message = message.get("newValue", {}).get("statusDates", {}).get("GA")
        else:
            date_from_message = message.get("newValue", {}).get("estimatedLaunchDate")

        try:
            item_attrs["date"] = self.get_date_iso_string_from_epoch_milliseconds_timestamp(timestamp=date_from_message)
        except (TypeError):
            logger.warning("region contains an unreadable date: {}".format(message))


        instance = self.get_region_instance_value(region_ac=region_ac, version=0)
        buildable_item = BuildableRegion(instance=instance, table=self.get_table(), **item_attrs)
        self.metrics = increment_metric(self.metrics, "region_change")
        return buildable_item


    def get_buildable_service(self, message):
        """
            Process a message about a change to a RIP service.  Return a BuildableService item.
            Sample message - see service_instance.json or new_service.json or new_component_service.json
        """

        rip_name = message["dimension"]["name"]
        parent_dimension_key = message.get("newValue").get("parentDimensionKey")

        if not parent_dimension_key:
            logger.info(f"Ingesting new Service '{rip_name}'!!!")
            item_attrs = self.get_attributes_from_new_value(map_of_attr_names=get_service_attributes_to_buildables_map(), new_value=message["newValue"])
            instance = self.get_service_instance_value(rip_name=rip_name, version=0)
        else:
            item_attrs = {}
            # parent_dimension_type can be: REGION, CELL, or SERVICE
            parent_dimension_type = parent_dimension_key["type"].upper()
            item_attrs["belongs_to_artifact"] = parent_dimension_type

            if parent_dimension_type == "REGION":
                parent_dimension_name = parent_dimension_key["name"].upper() # might not want this in SERVICE example - recon-integ
                item_attrs["belongs_to_instance"] = parent_dimension_name
                logger.info(f"Ingesting new service in region combo -> '{rip_name}' in '{parent_dimension_name}'")

                parent_exists = parent_object_exists(parent_dimension_type, parent_dimension_name)

                if not parent_exists:
                    logger.warning(f"Service in region is in a test, retail, or closed region and is not tracked. Parent region '{parent_dimension_name}' does not exist in database.")
                    return None

                instance = self.get_serviceinstance_instance_value(rip_name=rip_name, version=0, dimension_name=parent_dimension_name)
                item_attrs.update(self.get_attributes_from_new_value(
                    map_of_attr_names=get_service_attributes_to_buildables_map(),
                    new_value=message["newValue"]
                ))

                # we must guarantee all new service_instance objects have the same "plan" aka category as their parent MD object
                service_metadata_object = self.get_service_metadata(rip_name)
                if service_metadata_object:
                    parent_plan = service_metadata_object.get("plan")
                    if parent_plan:
                        logger.info(f"Found MD object for service '{rip_name}' with plan '{parent_plan}' - setting new instance '{parent_dimension_name}' to parent plan")
                        self.metrics = increment_metric(self.metrics, "pulled_plan_from_parent")
                        item_attrs["plan"] = parent_plan

                # we must save the date a service goes GA in a region as a separate field https://sim.amazon.com/issues/RECON-6126
                is_turning_ga = message.get('newValue', {}).get('status') == 'GA'
                old_value_isnt_ga = message.get('previousValue') is not None and message.get('previousValue', {}).get('status') != 'GA'
                should_save_launch_date = is_turning_ga and old_value_isnt_ga

                if should_save_launch_date:
                    logger.info(f"Service '{rip_name}' went GA in '{parent_dimension_name}' - saving its launch date")
                    self.metrics = increment_metric(self.metrics, "save_ga_launched_date")
                    item_attrs['ga_launched_date'] = self.get_date_iso_string_from_epoch_milliseconds_timestamp(timestamp=message["approvedDate"])
                    # If a service goes GA, we don't want to keep its confidence field. See https://issues.amazon.com/issues/RECON-6775.
                    item_attrs['confidence'] = None
                    self.metrics = increment_metric(self.metrics, 'remove_ga_confidence')

            elif parent_dimension_type == "SERVICE":
                parent_dimension_name = parent_dimension_key["name"]
                item_attrs["belongs_to_instance"] = parent_dimension_name
                logger.info(f"Ingesting new component service '{rip_name}' for parent '{parent_dimension_name}'")

                parent_exists = parent_object_exists(parent_dimension_type, parent_dimension_name)
                if not parent_exists:
                    logger.error(f"Component Services parent was not found in ddb. Parent name '{parent_dimension_name}'.")
                    return None

                instance = self.get_service_instance_value(rip_name=rip_name, version=0)
                item_attrs.update(
                    self.get_attributes_from_new_value(
                        map_of_attr_names=get_service_attributes_to_buildables_map(),
                        new_value=message["newValue"]
                    )
                )

            else:
                # we only handle services in REGIONS and SERVICES now, but may handle AZ/CELL/... in the future.
                self.metrics = increment_metric(self.metrics, "unsupported_parent_dimension")
                logger.warning("parent_dimension_type is {} - not doing anything!".format(parent_dimension_type))
                return None


        item_attrs["updated"] = self.get_date_iso_string_from_epoch_milliseconds_timestamp(timestamp=message["approvedDate"])
        item_attrs["updater"] = message["registrant"]
        buildable_item = BuildableService(instance=instance, table=self.get_table(), **item_attrs)
        self.metrics = increment_metric(self.metrics, "service_change")
        return buildable_item


    def get_service_metadata(self, service_name):
        """Return a dict of service metadata."""
        logger.debug("Getting metadata for service '{}'".format(service_name))
        params = {
            "ConsistentRead": False,
            "Key": {
                "artifact": "SERVICE",
                "instance": service_name + ":v0",
            }
        }

        service_metadata_response = execute_retryable_call(client=self.get_table(), operation="get_item", **params)
        logger.debug("service_metadata_response from ddb: {}".format(service_metadata_response))
        try:
            service_metadata = service_metadata_response["Item"]
            logger.debug("Returning service_metadata: {}".format(service_metadata))
            return service_metadata
        except (KeyError, TypeError):
            logger.info(f"No Service metadata found for '{service_name}'.. continuing")


    def get_sqs_client(self):
        if self.sqs_client is None:
            self.sqs_client = boto3.client('sqs')
        return self.sqs_client


    def delete_sqs_message(self, handle):
        logger.debug("Deleting handle {} from queue {}".format(handle, self.sqs_queue_url))
        with cloudwatch_timer(self.metrics, "delete_sqs"):
            self.get_sqs_client().delete_message(QueueUrl=self.sqs_queue_url, ReceiptHandle=handle)

    def cleanup_sqs(self, record):
        if record.receipt_handle:
            self.delete_sqs_message(handle=record.receipt_handle)
        elif not is_in_list_of_ignored_services(record.rip_name):
            logger.error(f"lambda was not invoked by sqs and service/region {record.rip_name} not in ignored allowlist")
            self.metrics = increment_metric(self.metrics, "lambda_not_invoked_by_sqs_or_tests")
        else:
            self.metrics = increment_metric(self.metrics, "integ_or_canary_execution")


    def write_to_dynamo(self):
        with self.get_table().batch_writer() as batch:
            for ddb_item in self.ddb_items_to_write:
                logger.debug("Writing item to dynamo: {}".format(ddb_item))
                batch.put_item(Item=ddb_item)

        with RegionMetadata.batch_write() as batch:
            for region_metadata in self.region_items_to_write:
                logger.debug(f"Writing region metadata to dynamo: {region_metadata.attribute_values}")
                batch.save(region_metadata)

        with ServiceMetadata.batch_write() as batch:
            for service_metadata in self.service_metadata_items_to_write:
                logger.debug(f"Writing service metadata to dynamo: {service_metadata.attribute_values}")
                batch.save(service_metadata)

        with ServicePlan.batch_write() as batch:
            for service_plan in self.service_plan_items_to_write:
                logger.debug(f"Writing service plan to dynamo: {service_plan.attribute_values}")
                batch.save(service_plan)

        self.metrics["ddb_items_written"] = len(self.ddb_items_to_write) + len(self.region_items_to_write) + len(self.service_metadata_items_to_write) + len(self.service_plan_items_to_write)
        self.ddb_items_to_write = []
        self.region_items_to_write = []
        self.service_metadata_items_to_write = []
        self.service_plan_items_to_write = []

    @staticmethod
    def get_date_iso_string_from_epoch_milliseconds_timestamp(timestamp):
        epoch = timestamp / 1000
        datetime_obj = datetime.datetime.fromtimestamp(epoch)
        return datetime_obj.isoformat()

    def get_attributes_from_new_value(self, map_of_attr_names, new_value):
        """
        Return a dict of item attributes and values.

        These item attributes will be written to the `buildables` table. This method will filter
        out attributes which shouldn't be written to our table.
        """
        buildable_item_attrs = {}
        for rip_attribute_to_get, buildable_item_key in map_of_attr_names.items():
            try:
                buildable_item_attrs[buildable_item_key] = new_value[rip_attribute_to_get]
                logger.debug("Got attribute from RIP: '{}={}'.  Setting buildable item attribute '{}={}'".format(rip_attribute_to_get,
                                                                                                                 new_value[rip_attribute_to_get],
                                                                                                                 buildable_item_key,
                                                                                                                 buildable_item_attrs[buildable_item_key]))
            except KeyError:
                # logger.debug("Message {} doesnt have attr '{}'".format(new_value, rip_attribute_to_get))
                pass
        return buildable_item_attrs
