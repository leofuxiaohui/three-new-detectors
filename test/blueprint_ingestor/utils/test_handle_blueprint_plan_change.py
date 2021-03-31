from unittest.mock import patch, Mock

import pytest

from regions_recon_lambda.blueprint_ingestor.data_records.plans_update import PlansToUpdate
from regions_recon_lambda.blueprint_ingestor.utils.handle_blueprint_plan_change import \
    handle_buildables_blueprint_received_plans, convert_buildables_blueprint_plans_to_plans, handle_unmatched_plans, \
    change_blueprint_plans
from regions_recon_python_common.data_models.plan import Plan


def create_mocked_buildables_blueprint_plan(plan: Plan):
    mocked_plan = Mock()
    mocked_plan.get_service.return_value = plan.service
    mocked_plan.get_region.return_value = plan.region
    return mocked_plan


LAMBDA_PLAN = Plan("lambda", "IAD")
SAGEMAKER_PLAN = Plan("sagemaker", "PDX")
DDB_PLAN = Plan("dynamodb", "SFO")

UID_TO_REMOVE_FROM_LAMBDA = "123"
UID_TO_REMOVE_FROM_SAGEMAKER = "234"
UID_TO_ADD_TO_DDB = "456"


@pytest.fixture
def test_buildables_blueprint_plans():
    return [
        create_mocked_buildables_blueprint_plan(LAMBDA_PLAN),
        create_mocked_buildables_blueprint_plan(SAGEMAKER_PLAN)
    ]


@pytest.fixture
def test_plans_to_update():
    plans_to_update = PlansToUpdate()
    plans_to_update.remove_uid_from_plans(UID_TO_REMOVE_FROM_LAMBDA, [LAMBDA_PLAN])
    plans_to_update.update_or_add_uid_to_plans(UID_TO_REMOVE_FROM_SAGEMAKER, [SAGEMAKER_PLAN])
    plans_to_update.update_or_add_uid_to_plans(UID_TO_ADD_TO_DDB, [DDB_PLAN])
    return plans_to_update


def test_handle_buildables_blueprint_received_plans(test_buildables_blueprint_plans, test_plans_to_update):
    handle_buildables_blueprint_received_plans(test_buildables_blueprint_plans, test_plans_to_update)
    assert test_buildables_blueprint_plans[0].add_uids.call_args[0][0] == frozenset()
    assert test_buildables_blueprint_plans[0].remove_uids.call_args[0][0] == frozenset([UID_TO_REMOVE_FROM_LAMBDA])
    test_buildables_blueprint_plans[0].recalculate.assert_called_once()

    assert test_buildables_blueprint_plans[1].add_uids.call_args[0][0] == frozenset([UID_TO_REMOVE_FROM_SAGEMAKER])
    assert test_buildables_blueprint_plans[1].remove_uids.call_args[0][0] == frozenset()
    test_buildables_blueprint_plans[1].recalculate.assert_called_once()


def test_buildables_blueprint_plans_to_plans(test_buildables_blueprint_plans):
    assert convert_buildables_blueprint_plans_to_plans([]) == set()
    assert convert_buildables_blueprint_plans_to_plans(test_buildables_blueprint_plans) == {LAMBDA_PLAN, SAGEMAKER_PLAN}


@patch("regions_recon_lambda.blueprint_ingestor.utils.handle_blueprint_plan_change.BlueprintPlan", autospec=True)
def test_handle_unmatched_plans(mocked_blueprint_plan, test_plans_to_update):
    plans = [SAGEMAKER_PLAN, DDB_PLAN]
    mocked_sagemaker_buildables_blueprint_plan = Mock()
    mocked_ddb_buildables_blueprint_plan = Mock()
    mocked_blueprint_plan.create.side_effect = [
        mocked_sagemaker_buildables_blueprint_plan,
        mocked_ddb_buildables_blueprint_plan
    ]

    handle_unmatched_plans(plans, test_plans_to_update)
    assert mocked_sagemaker_buildables_blueprint_plan.add_uids.call_args[0][0] == frozenset({UID_TO_REMOVE_FROM_SAGEMAKER})
    assert mocked_ddb_buildables_blueprint_plan.add_uids.call_args[0][0] == frozenset({UID_TO_ADD_TO_DDB})

    mocked_sagemaker_buildables_blueprint_plan.recalculate.assert_called_once()
    mocked_ddb_buildables_blueprint_plan.recalculate.assert_called_once()


@patch("regions_recon_lambda.blueprint_ingestor.utils.handle_blueprint_plan_change.handle_unmatched_plans", autospec=True)
@patch("regions_recon_lambda.blueprint_ingestor.utils.handle_blueprint_plan_change.handle_buildables_blueprint_received_plans", autospec=True)
@patch("regions_recon_lambda.blueprint_ingestor.utils.handle_blueprint_plan_change.BlueprintPlan", autospec=True)
def test_change_blueprint_plans(mocked_blueprint_plan,
                                mocked_handle_buildables_blueprint_received_plans,
                                mocked_handle_unmatched_plans,
                                test_buildables_blueprint_plans,
                                test_plans_to_update):
    mocked_blueprint_plan.batch_get.return_value = test_buildables_blueprint_plans
    change_blueprint_plans(test_plans_to_update)
    assert mocked_handle_buildables_blueprint_received_plans.call_args[0][0] == test_buildables_blueprint_plans
    assert mocked_handle_unmatched_plans.call_args[0][0] == {DDB_PLAN}
