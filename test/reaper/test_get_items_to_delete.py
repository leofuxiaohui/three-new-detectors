from unittest.mock import patch, Mock, MagicMock

from regions_recon_lambda.reaper.get_items_to_delete import RECON_INTEG_VERSION_DELETION_THRESHOLD, \
    reset_recon_service_plans, reset_recon_service_metadata, \
    write_and_reset_service_item


def test_write_and_reset_service_item():
    mock_service_type = MagicMock()
    mock_service_to_reset = Mock()
    mock_service_to_reset_two = Mock()

    mock_items_to_reset = [mock_service_to_reset, mock_service_to_reset_two]

    write_and_reset_service_item(mock_service_type, mock_items_to_reset)

    mock_service_type.batch_write().__enter__().save.assert_called()
    assert mock_service_to_reset.version_latest == RECON_INTEG_VERSION_DELETION_THRESHOLD
    assert mock_service_to_reset_two.version_latest == RECON_INTEG_VERSION_DELETION_THRESHOLD


@patch("regions_recon_lambda.reaper.get_items_to_delete.ServicePlan")
def test_reset_recon_service_plans(mock_service_plan):
    mock_plan = Mock()
    mock_service_plan.version_latest = -1  # needed to avoid filter comparison issue
    mock_service_plan.query.return_value = [mock_plan]

    reset_recon_service_plans()
    assert mock_plan.version_latest == RECON_INTEG_VERSION_DELETION_THRESHOLD
    assert mock_service_plan.batch_write().__enter__().save.called_with(mock_plan)


@patch("regions_recon_lambda.reaper.get_items_to_delete.ServiceMetadata")
def test_reset_recon_service_metadata(mock_service_metadata):
    mock_service_to_reset = Mock()
    mock_service_to_reset.version_latest = 20
    mock_service_not_to_reset = Mock()
    mock_service_not_to_reset.version_latest = 10

    mock_service_metadata.batch_get.return_value = [mock_service_to_reset, mock_service_not_to_reset]

    reset_recon_service_metadata()
    assert mock_service_to_reset.version_latest == RECON_INTEG_VERSION_DELETION_THRESHOLD
    assert mock_service_not_to_reset.version_latest != RECON_INTEG_VERSION_DELETION_THRESHOLD
    assert mock_service_metadata.batch_write().__enter__().save.called_with(mock_service_to_reset)
