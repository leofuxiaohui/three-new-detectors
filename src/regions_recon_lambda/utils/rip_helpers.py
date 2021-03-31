from typing import Iterable
from rip_helper.enums import Status, Visibility
from rip_helper.exceptions import ServiceNotFoundError
from rip_helper_local import RIPHelperLocal
from regions_recon_python_common.utils.log import get_logger

def get_internal_services(service_identifiers: Iterable[str]=[]):
    logger = get_logger()
    helper = RIPHelperLocal(metapackage="RIPDataAllSQLite-1.0")
    services = []

    # Check in case future use involves grabbing all internal services
    if service_identifiers:
        for identifier in service_identifiers:
            try:
                if helper.service(identifier).visibility == Visibility.INTERNAL:
                    services.append(identifier)
            except ServiceNotFoundError:
                logger.warning(f"The service identifier, \"{identifier}\", could not be found. {ServiceNotFoundError}")

    return services