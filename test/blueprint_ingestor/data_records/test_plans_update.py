import pytest

from regions_recon_lambda.blueprint_ingestor.data_records.plans_update import Update, PlansToUpdate
from regions_recon_python_common.data_models.plan import Plan


def test_handle_uid_remove():
    test_update = Update()
    test_update.handle_uid("123", True)
    assert "123" in test_update.remove_uids


def test_handle_uid_add():
    test_update = Update()
    test_update.handle_uid("123", False)
    assert "123" in test_update.update_or_add_uids


TEST_PLANS = [
    Plan("SERVICE_ONE", "IAD"),
    Plan("SERVICE_TWO", "PDX")
]


@pytest.fixture
def test_plans_to_update():
    return PlansToUpdate()


def test_plans_to_update_remove(test_plans_to_update):
    test_plans_to_update.remove_uid_from_plans("123", TEST_PLANS)
    assert "123" in test_plans_to_update.get_uids_to_remove(TEST_PLANS[0])
    assert "123" in test_plans_to_update.get_uids_to_remove(TEST_PLANS[1])


def test_plans_to_update_add_updated(test_plans_to_update):
    test_plans_to_update.update_or_add_uid_to_plans("123", TEST_PLANS)
    assert "123" in test_plans_to_update.get_update_or_add_uids(TEST_PLANS[0])
    assert "123" in test_plans_to_update.get_update_or_add_uids(TEST_PLANS[1])


def test_keys(test_plans_to_update):
    test_plans_to_update.update_or_add_uid_to_plans("123", TEST_PLANS)
    assert list(test_plans_to_update.keys()) == TEST_PLANS
