from unittest import mock
from regions_recon_lambda.utils import recon_helpers as recon
from regions_recon_lambda.utils.constants import ServicePlan

def mock_plan_fetch(*args):
    mock_recon_data = {
        "services/ecytu/plans": {
            "service": {
                    "plan": "Globally Expanding - Launch Blocking",
            }
        },
        "services/stree/plans": {
            "service": {
                    "plan": "Globally Expanding - Mandatory",
            }
        },
        "services/llamada/plans": {
            "service": {
                    "plan": "Non-Globally Expanding",
            }
        },
        "services/will_iam/plans": {
            "service": {
                    "changed_attributes": ["plan"]
            }
        }
    }

    return mock_recon_data[args[2]]


@mock.patch('regions_recon_lambda.utils.recon_helpers.get_aws_auth')
@mock.patch('regions_recon_lambda.utils.recon_helpers.get_recon_data')
@mock.patch('regions_recon_lambda.utils.rms_helpers.get_logger')
def test_find_plan(mock_logger, mock_get_recon_data, mock_get_aws_auth):
    mock_get_recon_data.side_effect = mock_plan_fetch
    mock_get_aws_auth.return_value = mock.Mock()

    assert recon.find_plan("ecytu") == ServicePlan.LAUNCH_BLOCKING
    assert recon.find_plan("stree") == ServicePlan.MANDATORY
    assert recon.find_plan("llamada") == ServicePlan.NON_GLOBAL
    assert recon.find_plan("will_iam") == ServicePlan.NON_GLOBAL
