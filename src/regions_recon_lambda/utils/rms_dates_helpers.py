import re
from datetime import datetime, timezone, timedelta
import dateparser
import pytz

from regions_recon_python_common.utils.constants import RIP_S_NAME_REGEX
from regions_recon_lambda.utils.constants import RIP_SERVICE_PREFIX, RIP_FEATURE_PREFIX


def valid_date(date):
    return len(date.split("-")) == 3


def days_between(d1: str, d2: str) -> int:
    d1 = datetime.strptime(d1, "%Y-%m-%d")
    d2 = datetime.strptime(d2, "%Y-%m-%d")
    return (d2 - d1).days


# returns date in YYYY-MM-DD string format or '-' if that's what was passed in
def get_short_date(date: str) -> str:
    if date == '-':
        return date

    date = dateparser.parse(date, settings={'DATE_ORDER': 'YMD'})

    if date.tzinfo is None or date.tzinfo.utcoffset(date) is None:
        date = pytz.utc.localize(date)

    date = date.astimezone(pytz.timezone('US/Pacific'))

    date = date.strftime('%Y-%m-%d')

    return date


def validate_service_name(svcname, logger):
    is_valid = False
    matches_re = re.search(RIP_S_NAME_REGEX, svcname)
    valid_len = len(svcname) < 200

    if (svcname is not None and matches_re and valid_len):
        is_valid = True
    else:
        logger.error("Something went wrong while validating servicename: {}".format(svcname))

    return is_valid


def validate_airport_code(arptcode, logger):
    is_valid = False
    matches_re = re.search("^[A-Z]{3}$", arptcode)  # need to test this one

    if (arptcode is not None and matches_re):
        is_valid = True
    else:
        logger.error("issue validating airport code: {}".format(arptcode))

    return is_valid


def validate_rms_milestone(milestone, logger):
    is_valid = True

    # Remove second condition in below line when RMS TTL is expired (currently getting v1 and v2 namespaces)
    if milestone.get("milestone_type") == "RIP_SERVICE" and (RIP_SERVICE_PREFIX in milestone.get("namespace") or RIP_FEATURE_PREFIX in milestone.get("namespace")):
        for key in ["namespace", "region", "service", "status", "early_finish"]:
            if key not in milestone.keys():
                is_valid = False
                logger.error("rms milestone came back invalid")
                break

    else:
        is_valid = False

    return is_valid
