from typing import Iterable

from regions_recon_python_common.buildables_dao_models.buildables_item import BuildablesItem
from regions_recon_python_common.utils.log import get_logger

logger = get_logger()


def delete_items(items_to_delete: Iterable[BuildablesItem]) -> int:
    deleted_items_count = 0

    with BuildablesItem.batch_write() as batch:
        for item in items_to_delete:
            logger.info(f"Deleted {item}")
            batch.delete(item)
            deleted_items_count += 1

    return deleted_items_count
