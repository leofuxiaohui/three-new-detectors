from unittest.mock import Mock, MagicMock

import pytest
from blueprint_ingestor.mocked_blueprint_data import TEST_BLUEPRINT_DATA

from regions_recon_lambda.blueprint_ingestor.dao.blueprint_dao import BlueprintDAO, \
    BLUEPRINT_EXPECTED_HEADERS
from regions_recon_lambda.blueprint_ingestor.exceptions import BlueprintAPIException
from regions_recon_python_common.utils.object_utils import deep_get

TEST_TIMESTAMP = "01/01/2020 01:20:04 PM"


def get_test_empty_blueprint_response():
    return {
        "ResponseMetadata": {
            "HTTPStatusCode": 200
        },
        "results": {
            "results": {
                "headers": [{"name": header} for header in BLUEPRINT_EXPECTED_HEADERS],
                "rows": []
            }
        }
    }


class StubHoneycodeClient:
    @staticmethod
    def get_screen_data(**kwargs) -> dict:
        rows = []
        response = get_test_empty_blueprint_response()

        token = kwargs.get("nextToken")

        if token is None:
            rows = TEST_BLUEPRINT_DATA["results"]["rows"][0:2]
            response["nextToken"] = 1

        elif token == 1:
            rows = [TEST_BLUEPRINT_DATA["results"]["rows"][2]]
            response["nextToken"] = 2

        elif token == 2:
            # final page, no need to add a nextToken
            rows = [TEST_BLUEPRINT_DATA["results"]["rows"][3]]

        response["results"]["results"]["rows"] = rows

        return response


def test_blueprint_dao_iterator_with_no_data():
    def get_empty_page(**kwargs):
        return get_test_empty_blueprint_response()

    client = Mock()
    client.get_screen_data = MagicMock(side_effect=get_empty_page)
    assert [] == [item for item in BlueprintDAO(client).get_iterator(TEST_TIMESTAMP)]


def test_blueprint_dao_iterator_with_data():
    client = StubHoneycodeClient()

    ids = [
        item[7]["formattedValue"]
        for item in BlueprintDAO(client).get_iterator(TEST_TIMESTAMP)
    ]
    expected_ids = {"10265", "10266", "10281", "10288"}

    assert len(ids) == 4
    assert set(ids) == expected_ids


def test_blueprint_dao_with_400_http_error():
    response = get_test_empty_blueprint_response()
    response["ResponseMetadata"]["HTTPStatusCode"] = 400

    client = Mock()
    client.get_screen_data = Mock(return_value=response)

    with pytest.raises(BlueprintAPIException):
        BlueprintDAO(client).get_iterator(TEST_TIMESTAMP)


def test_blueprint_dao_with_invalid_headers():
    response = get_test_empty_blueprint_response()
    deep_get(response, ("results", "results", "headers")).append({"name": "ILLEGAL HEADER"})

    client = Mock()
    client.get_screen_data = Mock(return_value=response)

    with pytest.raises(BlueprintAPIException):
        BlueprintDAO(client).get_iterator(TEST_TIMESTAMP)
