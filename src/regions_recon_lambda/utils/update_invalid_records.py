from typing import FrozenSet

from regions_recon_python_common.buildables_dao_models.blueprint_invalid_record import BlueprintInvalidRecord


def clear_no_longer_invalid_records(uids: FrozenSet[str]):
    invalid_records = BlueprintInvalidRecord.batch_get([
        BlueprintInvalidRecord.get_key(uid)
        for uid in uids
    ])

    for invalid_record in invalid_records:
        invalid_record.delete()
