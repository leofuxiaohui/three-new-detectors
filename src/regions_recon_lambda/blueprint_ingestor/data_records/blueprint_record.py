from datetime import datetime
from typing import FrozenSet

from dataclasses import dataclass

BLUEPRINT_EST_LAUNCH_DATE_FORMAT = "%m/%d/%y"
BLUEPRINT_LAST_UPDATED_DATE_FORMAT = "%m/%d/%y %H:%M"
BLUEPRINT_REGION_DELIMITER = ";"
BLUEPRINT_REGION_AIRPORT_CODE_DELIMITER = "-"
SERVICE_NAME_TO_IGNORE = "aws-launch-programs"
DRAFT_STATE = "Draft"
CANCELLED_STATE = "Cancelled"


@dataclass(frozen=True)
class BlueprintRecord:
    service_rip_short_name: str
    est_launch_date: str
    last_updated_date: str
    updater_email: str
    confidence: str
    state: str
    note: str
    uid: str
    regions: str

    def should_ignore(self) -> bool:
        is_draft = self.state == DRAFT_STATE
        should_ignore_service_name = self.service_rip_short_name == SERVICE_NAME_TO_IGNORE
        is_cancelled_without_last_updated_date = not self.last_updated_date and self.state == CANCELLED_STATE
        return any((is_draft, should_ignore_service_name, is_cancelled_without_last_updated_date))

    def get_validation_errors(self) -> FrozenSet[str]:
        validation_errors = set()

        try:
            datetime.strptime(self.last_updated_date, BLUEPRINT_LAST_UPDATED_DATE_FORMAT)
        except ValueError:
            validation_errors.add(f"Last updated date <{self.last_updated_date}> "
                                  f"is not correctly formatted <{BLUEPRINT_LAST_UPDATED_DATE_FORMAT}>.")

        try:
            datetime.strptime(self.est_launch_date, BLUEPRINT_EST_LAUNCH_DATE_FORMAT)
        except ValueError:
            validation_errors.add(f"Est launch date <{self.est_launch_date}> "
                                  f"is not correctly formatted <{BLUEPRINT_EST_LAUNCH_DATE_FORMAT}>.")

        if self.service_rip_short_name == "":
            validation_errors.add("The service name is empty")

        if self.note == "Test" or self.note == "test":
            validation_errors.add(f"The note is \"{self.note}\", test data should not be in the Blueprint API")

        for region in self.get_airport_codes():
            if len(region) != 3:
                validation_errors.add(f"The region string <{self.regions}> does not have 3-letter airport codes")

        return frozenset(validation_errors)

    def get_airport_codes(self) -> FrozenSet[str]:
        return frozenset((
            region.split(BLUEPRINT_REGION_AIRPORT_CODE_DELIMITER)[0].strip()
            for region in self.regions.split(BLUEPRINT_REGION_DELIMITER)
        ))

    def est_launch_date_to_datetime(self) -> datetime:
        return datetime.strptime(self.est_launch_date, BLUEPRINT_EST_LAUNCH_DATE_FORMAT)

    def last_updated_date_to_datetime(self) -> datetime:
        return datetime.strptime(self.last_updated_date, BLUEPRINT_LAST_UPDATED_DATE_FORMAT)
