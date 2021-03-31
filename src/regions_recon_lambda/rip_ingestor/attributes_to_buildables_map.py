def get_service_attributes_to_buildables_map():
    """
    Return a map of RIP attribute names to extract from the newValue map sent from RIP SNS.

    Keys here are the attributes which will eventually make their way to `buildable` items.
    Values are the attribute name we'll use for the `buildable` items.
    """
    return {
        "status": "status",
        "description": "description",
        "longName": "name_long",
        "visibility": "visibility",
        "availabilityLevel": "availability_level",
    }


def get_region_attributes_to_buildables_map():
    """
    Return a map of RIP attribute names to extract from the newValue map sent from RIP SNS.

    Keys here are the attributes which will eventually make their way to `buildable` items.
    Values are the attribute name we'll use for the `buildable` items.
    """
    return {
        "arnPartition": "partition",
        "codeName": "name_codename",
        "longName": "description",
        "regionName": "name_long",
        "status": "status",
        "accessibilityAttributes": "accessibility_attributes",
        "tags": "tags"
    }
