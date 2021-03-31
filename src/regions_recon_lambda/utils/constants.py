from enum import Enum
# how many seconds to cache our item in DDB
DEFAULT_CACHE_EXPIRY = 600
RMS_CACHE_EXPIRY = DEFAULT_CACHE_EXPIRY
PAWPRINT_CACHE_EXPIRY = 86400  # pawprint data is only published once per day
PAWPRINT_BUCKET_NAME = "pawprint-export-prod"

# https://docs.python.org/3/library/gzip.html#module-gzip
CACHE_GZIP_COMPRESSION_LEVEL = 9


# RMSDatesScheduledJob
RIP_FEATURE_PREFIX = "arn:aws:rip:::instance/feature/"
RIP_SERVICE_PREFIX = "arn:aws:rip:::instance/service/"

RIP_SERVICE_STATUS_INDEX = 2
RIP_FEATURE_STATUS_INDEX = 3

AWS_HOST_RMSV2 = "8bphrxrhw0.execute-api.us-east-1.amazonaws.com"
AWS_HOST_RECON = "api.recon.region-services.aws.a2z.com"
AWS_HOST_RECON_BETA = "api.recon-beta.region-services.aws.a2z.com"
AWS_RMS_ANALYTICS = "api.analytics.rms.region-services.aws.a2z.com"
AWS_REGION_EAST = "us-east-1"

LAUNCH_BLOCKING_MILESTONE_ARN = "arn:aws:rmsv2:::milestone/26ab1cff-e0b3-49d8-82a4-efd6e5e2b677"
MANDATORY_MILESTONE_ARN = "arn:aws:rmsv2:::milestone/b05fdb54-ff54-44e9-9549-9085402268ed"

class ServicePlan(Enum):
    LAUNCH_BLOCKING = "Globally Expanding - Launch Blocking"
    MANDATORY = "Globally Expanding - Mandatory"
    NON_GLOBAL = "Non-Globally Expanding"
    UNCATEGORIZED = "UNCATEGORIZED"

class RmsEndpoint(Enum):
    MT = "milestones/tasks"
    MILESTONES = "milestones"
    TASKS = "tasks"
    EDGES = "edges"
