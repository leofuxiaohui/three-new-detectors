from regions_recon_lambda.blueprint_ingestor.utils.plan_update_utils import determine_plans_to_remove
from regions_recon_python_common.data_models.plan import Plan


def test_determine_plans_to_remove_same_service_same_regions():
    service = "TEST"
    regions = frozenset(["IAD", "PDX"])

    assert not determine_plans_to_remove(service, regions, service, regions)


def test_determine_plans_to_remove_different_service_same_regions():
    old_service = "OLD SERVICE"
    new_service = "NEW SERVICE"
    regions = frozenset(["IAD", "PDX"])

    assert determine_plans_to_remove(old_service, regions, new_service, regions) == frozenset([
        Plan(old_service, "IAD"),
        Plan(old_service, "PDX")
    ])


def test_determine_plans_to_remove_same_service_different_region():
    service = "TEST"
    old_regions = frozenset(["IAD", "PDX"])
    new_regions = frozenset(["PDX", "SFO"])

    assert determine_plans_to_remove(service, old_regions, service, new_regions) == frozenset([
        Plan(service, "IAD")
    ])
