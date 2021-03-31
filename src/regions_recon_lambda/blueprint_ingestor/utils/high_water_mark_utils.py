from typing import Optional

from regions_recon_python_common.buildables_dao_models.blueprint_high_water_mark import BlueprintHighWaterMark

TIMESTAMP_TO_GET_ALL_BLUEPRINT_RECORDS = "01/01/2010 01:20:04 PM"


def get_high_water_mark_or_default() -> str:
    high_water_mark: Optional[BlueprintHighWaterMark] = BlueprintHighWaterMark.get_if_present()
    return high_water_mark.to_blueprint_format() if high_water_mark else TIMESTAMP_TO_GET_ALL_BLUEPRINT_RECORDS
