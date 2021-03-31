from typing import Set
import re
from regions_recon_python_common.buildables_ingestor import BuildablesIngestor
from regions_recon_python_common.utils.misc import execute_retryable_call
from boto3.dynamodb.conditions import Key, Attr
from regions_recon_python_common.utils.log import get_logger
logger = get_logger()


# Regular expression literal that matches all services that we should ignore.
# We haven't followed a good pattern in the past, so this is /predictive/ instead
# of /proscriptive/.  There aren't any rules, so this guesses as best as it can.
# All ignorable services seem to start with "recon", so we anchor that.  They also
# all contain "integ".  To be safe, this brackets them with "[^a-z]" which matches
# only non-letters.  This guards against a service named "reconcile" with "integration"
# in the name too.
SERVICES_TO_IGNORE = r"""^ recon        # must start with 'recon'
                           [^a-z]       # non-letter so doesn't match "reconcile"
                           (.*[^a-z])?  # optionally a bunch more that ends in non-letter
                           integ        # line above prevents "blahinteg" word prefixes
                           ([^a-z].*)?  # nothing else, or stuff that starts with non-letter
                         $
                      """


def ignore_service(name: str) -> bool:
    """separate function so the logic can be unit-tested in isolation"""
    return re.match(SERVICES_TO_IGNORE, name, re.IGNORECASE | re.X) is not None


def validate_ddb_data(event, context):
    logger.debug("event: {}".format(event))
    logger.debug("context: {}".format(context.__dict__))

    validator = DDBDataIntegrityValidator(metrics_service_name=context.function_name)
    validator.run_workflow()

class DDBDataIntegrityValidator(BuildablesIngestor):
    def __init__(self, metrics_service_name):
        self.metrics = {}
        self.metrics_service_name = metrics_service_name

    def get_all_query_results(self, query_params): # TODO - this should be pulled out into BuildablesIngestor
        """Return all items from a query.  This handles pagination."""
        logger.debug("Getting all results for query '{}'".format(query_params))
        items = []
        while True:
            resp = execute_retryable_call(client=self.get_table(), operation="query", **query_params)
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

    def run_workflow(self):
        logger.info("Running workflow - ensure all categorized service instances have 'plan' attr")
        all_data_issues = []
        metadata_params = {
            "IndexName": "artifact-plan-index",
            "KeyConditionExpression": Key("artifact").eq("SERVICE"),
            "FilterExpression": Attr("belongs_to_instance").not_exists() & Attr("version_instance").eq(0)
        }
        cat_services_metadata = self.get_all_query_results(metadata_params)

        for service_object in cat_services_metadata:
            service_name = service_object["instance"].split(":")[0]
            if ignore_service(service_name):
                logger.info(f"Skipping service {service_name}")
            else:
                service_cat = service_object["plan"]
                logger.info(f"Checking '{service_name}' with cat '{service_cat}'")

                # Now we need to get all the instances for the service
                # DONT use "IndexName": "artifact-plan-index" - that would defeat the purpose of the test..
                params = {
                    "KeyConditionExpression":
                        Key("artifact").eq("SERVICE") & Key("instance").begins_with(f"{service_name}:v0:")
                }
                service_instances = self.get_all_query_results(params)

                for instance in service_instances:
                    region = instance.get("belongs_to_instance")
                    has_plan = instance.get("plan")
                    if not has_plan:
                        logger.error(f"error - No 'plan' attribute found for '{service_name}' in '{region}'")
                        all_data_issues.append(instance)
                    else:
                        logger.debug(f"no issues with {region}")


        if len(all_data_issues) > 0:
            raise Exception(f"plan-index not in sync - too many errors {len(all_data_issues)} - make sure all instances have 'plan' attr: {all_data_issues}")
        else:
            logger.info("No issues found! 🎉✅")


def _is_service_instance(service):
    return "belongs_to_artifact" in service.keys()

def _is_categorized_service(service):
    return "plan" in service.keys()
