from unittest.mock import MagicMock, Mock, patch

from regions_recon_lambda.reaper.delete import delete_items


@patch('regions_recon_lambda.reaper.delete.BuildablesItem.batch_write', autospec=True)
def test_delete_items(mocked_batch_write):
    mocked_writer = MagicMock()
    mocked_writer.__enter__.return_value = mocked_writer
    mocked_batch_write.return_value = mocked_writer

    assert delete_items([]) == 0
    assert delete_items([Mock()]) == 1
    assert delete_items([Mock(), Mock()]) == 2
