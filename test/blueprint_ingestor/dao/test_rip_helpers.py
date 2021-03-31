import unittest
import pytest
from mock_logger import MockLogger
from regions_recon_lambda.utils import rip_helpers as rip
from unittest.mock import Mock
from rip_helper_local import RIPHelperLocal
from rip_helper.enums import Status, Visibility
from rip_helper.exceptions import ServiceNotFoundError

class MockServiceMetadata:
    def __init__(self, visibility):
        self.visibility = visibility
    
    def visibility(self):
        return self.visibility

class MockRIPHelperLocal:
    def __init__(self, **kwargs):
        self.services = {
            "ecytu": MockServiceMetadata(Visibility.INTERNAL),
            "stree": MockServiceMetadata(Visibility.INTERNAL),
            "llamada": MockServiceMetadata(Visibility.INTERNAL),
            "cloudcondensation": MockServiceMetadata(Visibility.INTERNAL),
            "netsky": MockServiceMetadata(Visibility.EXTERNAL),
            "cloudobserve": MockServiceMetadata(Visibility.EXTERNAL),
            "nightshift": MockServiceMetadata(Visibility.INTERNAL),
            "will_iam": MockServiceMetadata(Visibility.EXTERNAL),
        }
    
    def service(self, service_identifier):
        if service_identifier in self.services:
            return self.services[service_identifier]
        else:
            raise ServiceNotFoundError(service_identifier)

@unittest.mock.patch('regions_recon_lambda.utils.rms_helpers.get_logger')
@unittest.mock.patch('regions_recon_lambda.utils.rip_helpers.RIPHelperLocal', autospec=MockRIPHelperLocal)
def test_get_internal_services_with_mixed_list(rip_helper, mock_logger):
    mock_logger.return_value = MockLogger()
    mock_rip_helper = MockRIPHelperLocal()
    rip_helper.return_value.service.side_effect = mock_rip_helper.service
    mocked_service_identifiers = [
        "ecytu", "stree", "cloudcondensation", "will_iam", "netsky", "sword", "nirvana", "llamada"
    ]
    expected_services = ["ecytu", "stree", "cloudcondensation", "llamada"]
    assert rip.get_internal_services(mocked_service_identifiers) == expected_services

@unittest.mock.patch('regions_recon_lambda.utils.rms_helpers.get_logger')
@unittest.mock.patch('regions_recon_lambda.utils.rip_helpers.RIPHelperLocal', autospec=MockRIPHelperLocal)
def test_get_internal_services_empty_list(rip_helper, mock_logger):
    mock_logger.return_value = MockLogger()
    mock_rip_helper = MockRIPHelperLocal()
    rip_helper.return_value.service.side_effect = mock_rip_helper.service
    mocked_service_identifiers = []
    expected_services = []
    assert rip.get_internal_services(mocked_service_identifiers) == expected_services

@unittest.mock.patch('regions_recon_lambda.utils.rms_helpers.get_logger')
@unittest.mock.patch('regions_recon_lambda.utils.rip_helpers.RIPHelperLocal', autospec=MockRIPHelperLocal)
def test_get_internal_services_externalonly_list(rip_helper, mock_logger):
    mock_logger.return_value = MockLogger()
    mock_rip_helper = MockRIPHelperLocal()
    rip_helper.return_value.service.side_effect = mock_rip_helper.service
    mocked_service_identifiers = [
        "will_iam", "cloudobserve", "netsky"
    ]
    expected_services = []
    assert rip.get_internal_services(mocked_service_identifiers) == expected_services
    