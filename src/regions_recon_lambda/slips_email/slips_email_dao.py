import os
import pprint
import logging
import json
from datetime import datetime, timezone, timedelta
from boto3.dynamodb.conditions import Key, Attr
from dateutil import parser
import pytz
from regions_recon_python_common.utils.cloudwatch_metrics_utils import submit_cloudwatch_metrics, increment_metric
from regions_recon_python_common.utils.constants import BUILDABLES_TABLE_NAME
from regions_recon_python_common.utils.log import get_logger
from regions_recon_lambda.utils.dynamo_query import DynamoQuery

CUTOFF_ARTIFACT = 'NOTIFICATION'
CUTOFF_INSTANCE = "region-slips"
NORMALIZED_DATE_FORMAT_WITH_SEC = "%Y-%m-%d %H:%M:%S %Z"


logger = get_logger()


class SlipsEmailDAO():
    def __init__(self):
        self.buildables = DynamoQuery(BUILDABLES_TABLE_NAME)
        self.should_validate = True   # to help with some tests


    def get_update_cutoff(self, minval):
        item = self.buildables.get_item(CUTOFF_ARTIFACT, CUTOFF_INSTANCE, [ 'updated' ])
        if item and 'updated' in item:
            updated = item['updated']
            try:
                val = parser.parse(updated).replace(tzinfo=pytz.UTC)
                return val if val > minval else minval
            except (TypeError, ValueError):
                logger.warning(
                    "Could not parse '%s' date in Dynamo table.  This is the high-water-mark for how far back to look.", updated)
        else:
            logger.warning("No high-water-mark in Dynamo (artifact=%s, instance=%s).", CUTOFF_ARTIFACT, CUTOFF_INSTANCE)

        return minval


    def set_update_cutoff(self):
        now_str = datetime.now(timezone.utc).strftime(NORMALIZED_DATE_FORMAT_WITH_SEC)
        self.buildables.update_item(CUTOFF_ARTIFACT, CUTOFF_INSTANCE, updated=now_str)
        logger.info("Updated high-water-mark to {}".format(now_str))


    def get_plan(self, service_key, version_instance, region_key):
        instance = "{}:v{}:{}".format(service_key, version_instance, region_key)
        plan = self.buildables.get_item('SERVICE', instance)
        if plan:
            self.validate_plans([plan])
        return plan


    def get_unlaunched_regions(self):
        now = datetime.now(timezone.utc).isoformat()
        items = self.buildables.query(
            Key("artifact").eq("REGION"),
            None,
            None,
            Attr('date').gt(now) & Attr('version_instance').eq(0))

        if len(items) == 0:
            logger.warn("No unlaunched regions to report on.")

        return [ item['instance'].split(':')[0]  for item in items ]


    def get_services_and_plans(self):
        """
        To be efficient, pull down everything (version 0) with artifact=SERVICE.  This is both services and
        plans.  Separate them after we have them in memory.  This way it's a single-pass through the table.
        """
        items = self.buildables.query(
            Key('artifact').eq('SERVICE'),
            None,
            'artifact-plan-index',
            Attr('version_instance').eq(0))

        services = []
        plans = []
        for item in items:
            if item.get('belongs_to_artifact') == 'REGION':
                plans.append(item)
            else:
                services.append(item)

        self.validate_services(services)
        self.validate_plans(plans)

        return (services, plans)


    def validate_services(self, services):
        if self.should_validate:
            for service in services:
                instance = self.get_required_attr(service, 'instance')
                service['rip_name'] = instance.split(':')[0]

                text = service['rip_name']
                if "name_sortable" in service:
                    text = service["name_sortable"]
                elif "name_sales" in service:
                    text = service["name_sales"]
                elif "name_marketing" in service:
                    text = service["name_marketing"]
                elif "name_long" in service:
                    text = service["name_long"]
                service['name_pretty'] = text

                self.get_required_attr(service, 'version_instance')


    def validate_plans(self, plans):
        if self.should_validate:
            for plan in plans:
                instance = self.get_required_attr(plan, 'instance')
                plan['rip_name'] = instance.split(':')[0]

                self.get_required_attr(plan, 'version_latest')
                self.get_required_attr(plan, 'version_instance')
                self.get_required_attr(plan, 'belongs_to_artifact')
                self.get_required_attr(plan, 'belongs_to_instance')

                if 'updated' in plan:
                    plan['updated'] = parser.parse(plan['updated']).replace(tzinfo=pytz.UTC)

                if 'date' in plan:
                    plan['date'] = parser.parse(plan['date']).replace(tzinfo=pytz.UTC)


    def get_required_attr(self, obj, attr_name):
        val = obj.get(attr_name)
        if val is None or len(str(val)) == 0:
            raise ValueError("Attribute {} was not found or empty in object {}".format(attr_name, obj))
        return val
