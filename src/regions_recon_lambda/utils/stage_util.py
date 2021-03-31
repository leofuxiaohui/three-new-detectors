import os

STAGE_KEY = "STAGE"
PROD_STAGE = "prod"
GAMMA_STAGE = "gamma"


def is_prod_stage() -> bool:
    """
    Note that the STAGE environment variable must be set
    :return: Whether the current stage is prod
    """
    return os.environ[STAGE_KEY] == PROD_STAGE


def is_gamma_or_prod_stage() -> bool:
    return os.environ[STAGE_KEY] in (PROD_STAGE, GAMMA_STAGE)
