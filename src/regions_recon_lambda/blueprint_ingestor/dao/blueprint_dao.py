from typing import List, Dict

from regions_recon_python_common.utils.log import get_logger

from regions_recon_lambda.blueprint_ingestor.exceptions import BlueprintAPIException
from regions_recon_python_common.utils.object_utils import deep_get


BLUEPRINT_SCREEN_ARGS = dict(
    workbookId='910865ba-efa8-44ad-acb4-247de2540df9',
    appId='1f43c1d8-76fe-4530-8bc2-2b20aab59123',
    screenId='d549aec8-bb09-33b5-b5c8-e5d034cb8e6f',
)


BLUEPRINT_EXPECTED_HEADERS = (
    "service_rip_short_name",
    "est_launch_date",
    "last_updated_date",
    "updater_email",
    "confidence",
    "state",
    "note",
    "uid",
    "regions"
)

logger = get_logger()


class BlueprintDAO:
    def __init__(self, honeycode_client):
        self.honeycode_client = honeycode_client

    def get_iterator(self, timestamp: str) -> "BlueprintIterator":
        return BlueprintIterator(self, timestamp)


class BlueprintIterator:
    def __init__(self, blueprint_dao: BlueprintDAO, timestamp: str):
        self.blueprint_dao: BlueprintDAO = blueprint_dao
        self.honeycode_args = dict(
            **BLUEPRINT_SCREEN_ARGS,
            variables={
                "Timestamp": {
                    "rawValue": timestamp
                }
            }
        )
        logger.info(f"Connecting to blueprint with timestamp: {timestamp}")
        self.items: List[List[Dict[str, str]]] = self.__process_results_page(self.__get_next_page())

    @staticmethod
    def __throw_exception_if_invalid_blueprint_response(response: dict) -> None:

        http_status_code = deep_get(response, ("ResponseMetadata", "HTTPStatusCode"))

        if http_status_code >= 400:
            raise BlueprintAPIException(f"Received an error HTTPStatusCode of {http_status_code}")

        headers = deep_get(response, ("results", "results", "headers"))
        header_values = tuple(header.get("name") for header in headers if "name" in header)

        if header_values != BLUEPRINT_EXPECTED_HEADERS:
            raise BlueprintAPIException(f"Blueprint headers: {headers} \n "
                                        f"do not match the expected headers of {BLUEPRINT_EXPECTED_HEADERS}")

    @staticmethod
    def __process_results_page(results_page: dict) -> List[List[Dict[str, str]]]:
        return [
            item["dataItems"]
            for item in results_page.get("results", {}).get("rows", [])
            if "dataItems" in item
        ]

    def __get_next_page(self) -> dict:
        logger.info("Getting next page of data items from Blueprint")
        response = self.blueprint_dao.honeycode_client.get_screen_data(**self.honeycode_args)
        logger.info(f"Received response from Blueprint: {response}")
        next_token_key = "nextToken"
        self.has_additional_pages = next_token_key in response
        if self.has_additional_pages:
            self.honeycode_args[next_token_key] = response[next_token_key]

        self.__throw_exception_if_invalid_blueprint_response(response)
        return response["results"]

    def __iter__(self) -> "BlueprintIterator":
        return self

    def __next__(self) -> List[Dict[str, str]]:
        if not self.items:
            raise StopIteration

        next_elem = self.items.pop()

        if not self.items and self.has_additional_pages:
            self.items = self.__process_results_page(self.__get_next_page())
            self.items.reverse()

        return next_elem
