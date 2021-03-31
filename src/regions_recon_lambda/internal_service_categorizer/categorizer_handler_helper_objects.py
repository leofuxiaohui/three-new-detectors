from typing import Dict
from regions_recon_lambda.utils.constants import ServicePlan

class RmsMilestoneOrTaskData:
    """
    Wraps the data returned from the RMS milestone or task endpoint with the plan of the
    service associated with the given milestone or task.

    @params
    rms_data: The json object for this milestone or task
    service_plan: The plan of the service that is associated with this milestone/task
    on_path_predecessor: The milestone/task arn that is this milestone/task's predecessor on a given categorization path
    """
    def __init__(self, rms_data: Dict[str, str], service_plan: ServicePlan = None, on_path_predecessor: str = None):
        self.rms_data = rms_data
        self.service_plan = service_plan
        self.on_path_predecessor = on_path_predecessor

    def get_arn(self):
        return self.rms_data["arn"]
    
    def get_service(self):
        return self.rms_data.get("service", "")

    def get_name(self):
        return self.rms_data.get("name", "N/A")

    def __eq__(self, other):
        if isinstance(other, RmsMilestoneOrTaskData):
            return self.__dict__ == other.__dict__
        return NotImplemented

    def __ne__(self, other):
        x = self.__eq__(other)
        if x is not NotImplemented:
            return not x
        return NotImplemented
