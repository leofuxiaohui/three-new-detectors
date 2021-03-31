import pytest
from regions_recon_lambda.ddb_data_integrity_validator import ignore_service


@pytest.mark.parametrize("name, should_ignore", [
    # This is the current list as of Feb 2021 that are integ services
    ('recon-integ', True),
    ('recon-integ+friday-test', True),
    ('recon-integ+recon-component-test-addilks', True),
    ('recon-integ+component-service', True),
    ('recon-integ+recon-component-monday-test', True),
    ('recon-integ+componentfeatures-modal-integ', True),
    ('recon-integ+componentfeatures-modal-integ+component-to-add-as-feature', True),
    ('recon-integ-2', True),
    ('recon-componentfeatures-modal-integ', True),
    ('recon-componentfeatures-modal-integ+component-to-add-as-feature', True),

    ('recon-integer', False),                # integ has to be followed by a non-letter
    ('recon?integ', True),                   # actual separator doesn't matter as long as it isn't a letter
    ('whatever-recon-integ', False),         # has to start with 'recon'
    ('reconinteg', False),                   # 'recon' and 'integ' have to be separate words
    ('reconcile-integ', False),              # 'recon' has to be followed by non-letter
    ('recon-fu-br-bz-q', False),             # doesn't have 'integ'
    ('integ', False),                        # doesn't start with 'recon'
    ('recon-recon-integ-inreg+integ', True), # good enough!  meets 'recon' and 'integ'
])
def test_ignore_service(name, should_ignore):
    assert ignore_service(name) == should_ignore
