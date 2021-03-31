from typing import List, Optional
from unittest.mock import Mock, patch

import pytest
from regions_recon_python_common.buildables_dao_models.service_plan import PlanByService, PLAN_BY_SERVICE_ARTIFACT

from regions_recon_lambda.rms_dates_ingestor.rms_dates_updater import get_service_plans_with_update, \
    update_service_plans, log_updated_rms_projected_dates
from regions_recon_lambda.rms_dates_ingestor.service_plan_update import ServicePlanUpdate


@pytest.fixture
def service_plans() -> List[PlanByService]:
    return [
        PlanByService(artifact=PLAN_BY_SERVICE_ARTIFACT, instance="lambda:IAD", rms_early_finish_date="2020-12-12"),
        PlanByService(artifact=PLAN_BY_SERVICE_ARTIFACT, instance="dynamodb:OSU", rms_early_finish_date="2020-01-01"),
        PlanByService(artifact=PLAN_BY_SERVICE_ARTIFACT, instance="s3:PDT"),
        PlanByService(artifact=PLAN_BY_SERVICE_ARTIFACT, instance="appconfig:CMH"),
    ]


@pytest.fixture
def rms_date_updates() -> List[Optional[str]]:
    return [
        "2020-02-02",
        "2020-01-01",
        None,
        "2020-03-03",
    ]


@pytest.fixture
def service_plan_updates(service_plans, rms_date_updates) -> List[ServicePlanUpdate]:
    # Only the first and last test_service_plans have different rms_early_finish_date values

    return [
        ServicePlanUpdate(service_plans[0], rms_date_updates[0]),
        ServicePlanUpdate(service_plans[3], rms_date_updates[3])
    ]


def test_get_service_plans_with_update_no_service_plans():
    assert get_service_plans_with_update([], Mock()) == []


@patch("regions_recon_lambda.rms_dates_ingestor.rms_dates_updater.get_rms_projected_ga_date_from_milestones")
@patch("regions_recon_lambda.rms_dates_ingestor.rms_dates_updater.get_rms_date_milestones")
def test_get_service_plans_with_update(get_rms_date_milestones,
                                       get_rms_projected_ga_date_from_milestones,
                                       service_plans,
                                       rms_date_updates,
                                       service_plan_updates):
    get_rms_projected_ga_date_from_milestones.side_effect = rms_date_updates
    assert get_service_plans_with_update(service_plans, Mock()) == service_plan_updates


@patch("regions_recon_lambda.rms_dates_ingestor.rms_dates_updater.PlanByService")
def test_update_service_plans(mock_service_plan, service_plan_updates):
    mock_service_plan.batch_get.return_value = [
        service_plan
        for service_plan, _ in service_plan_updates
    ]

    update_service_plans(service_plan_updates)

    assert len(mock_service_plan.batch_write().__enter__().save.call_args) == len(service_plan_updates)
    assert service_plan_updates[0].service_plan.rms_early_finish_date == service_plan_updates[0].rms_date_update
    assert service_plan_updates[1].service_plan.rms_early_finish_date == service_plan_updates[1].rms_date_update


@patch("regions_recon_lambda.rms_dates_ingestor.rms_dates_updater.metric_log_no_change_in_rms_projected_ga_date")
@patch("regions_recon_lambda.rms_dates_ingestor.rms_dates_updater.metric_log_change_in_rms_projected_ga_date")
def test_log_updated_rms_projected_dates(mock_metric_log_change_in_rms_projected_ga_date, mock_metric_log_no_change_in_rms_projected_ga_date):
    service_plans = [Mock(), Mock(), Mock(), Mock(), Mock()]
    updated = [Mock(), Mock(), Mock()]

    log_updated_rms_projected_dates(service_plans, updated)

    # 3 are updated out of 5, so 2 are not updated
    mock_metric_log_change_in_rms_projected_ga_date.assert_called_with(3)
    mock_metric_log_no_change_in_rms_projected_ga_date.assert_called_with(2)
