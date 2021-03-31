from typing import Set, Dict, Iterable, FrozenSet

from dataclasses import dataclass, field

from collections import defaultdict

from regions_recon_python_common.data_models.plan import Plan


@dataclass
class Update:
    update_or_add_uids: Set[str] = field(default_factory=set)
    remove_uids: Set[str] = field(default_factory=set)

    def handle_uid(self, uid: str, should_remove: bool):
        (self.remove_uids if should_remove else self.update_or_add_uids).add(uid)


class PlansToUpdate:
    def __init__(self):
        self.plans_to_update: Dict[Plan, Update] = defaultdict(Update)
        self.encountered_uids: Set[str] = set()

    def __handle_plans(self, uid: str, plans: Iterable[Plan], should_remove: bool):
        self.encountered_uids.add(uid)
        for plan in plans:
            self.plans_to_update[plan].handle_uid(uid, should_remove)

    def remove_uid_from_plans(self, uid: str, plans: Iterable[Plan]):
        self.__handle_plans(uid, plans, True)

    def update_or_add_uid_to_plans(self, uid: str, plans: Iterable[Plan]):
        self.__handle_plans(uid, plans, False)

    def keys(self):
        return self.plans_to_update.keys()

    def get_uids_to_remove(self, plan: Plan) -> FrozenSet[str]:
        return frozenset(self.plans_to_update[plan].remove_uids)

    def get_update_or_add_uids(self, plan: Plan) -> FrozenSet[str]:
        return frozenset(self.plans_to_update[plan].update_or_add_uids)

    def get_encountered_uids(self) -> FrozenSet[str]:
        return frozenset(self.encountered_uids)
