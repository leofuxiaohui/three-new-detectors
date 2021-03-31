from typing import NamedTuple

from regions_recon_python_common.buildables_dao_models.service_plan import PlanByService


class ServicePlanUpdate(NamedTuple):
    service_plan: PlanByService
    rms_date_update: str
