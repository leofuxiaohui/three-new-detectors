from unittest.mock import patch, Mock

from regions_recon_lambda.blueprint_ingestor.utils.update_invalid_records import clear_no_longer_invalid_records


@patch('regions_recon_lambda.blueprint_ingestor.utils.update_invalid_records.BlueprintInvalidRecord', autospec=True)
def test_clear_no_longer_invalid_records_zero_records(mocked_blueprint_invalid_record):
    mocked_blueprint_invalid_record.batch_get.return_value = []

    clear_no_longer_invalid_records(frozenset(("123", "234")))
    mocked_blueprint_invalid_record.get_key.assert_called()


@patch('regions_recon_lambda.blueprint_ingestor.utils.update_invalid_records.BlueprintInvalidRecord', autospec=True)
def test_clear_no_longer_invalid_records_two_records(mocked_blueprint_invalid_record):
    mocked_invalid_record_one = Mock()
    mocked_invalid_record_two = Mock()

    mocked_blueprint_invalid_record.batch_get.return_value = [
        mocked_invalid_record_one,
        mocked_invalid_record_two
    ]

    clear_no_longer_invalid_records(frozenset(("123", "234")))

    mocked_invalid_record_one.delete.assert_called_once()
    mocked_invalid_record_two.delete.assert_called_once()
