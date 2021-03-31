from typing import FrozenSet

from regions_recon_python_common.data_models.plan import Plan


def determine_plans_to_remove(old_service: str,
                              old_regions: FrozenSet[str],
                              new_service: str,
                              new_regions: FrozenSet[str]) -> FrozenSet[Plan]:
    region_difference = old_regions.difference(new_regions) if old_service == new_service else old_regions
    return Plan.generate_plans(old_service, region_difference)
