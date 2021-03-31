#  Slips Email Developer Info


## Arguments

Function `send_slips_email()` is ment to be called by AWS Lambda and it's arguments "event, context" match
the expected signature.  It doesn't use the "context" structure.

Below are attributes you can pass in `event` to control how `send_slips_email()` behaves:

**`debug`**: adding this (with any value) changes the logging level from INFO to DEBUG.  ***Warning***, this will add a
breathtaking amount of logging to the output (CloudWatch Logs), including a narrative about how all major decisions are
made in the logic.  This is good for troubleshooting, but bad for anything else.

**`dryrun`**: adding this (with any value) skips sending to MessageMultiplexer.  Great for debugging and development
to confirm the output matches expectations.

**`logmm`**: adding this (with any value) adds a single entry to the output CloudWatch Logs with a full "pretty-print"
of the argument sent to Message Multiplexer.

Setting `debug` also (effectively) sets `logmm`.


Example:

```json
send_slips_email({
    'debug': '',        # value isn't used, presence of any of these is sufficient
    'dryrun': None,
    'logmm': 'yes'
})
```


## General Logic

Overall, `send_slips_mail()` queries the `buildables` table for regions, services, and plans, and generates a JSON
structure it sends to to MessageMultiplexer (MM).  MM has the template that converts the JSON structure into a
human-formatted email message.

High-level logic:

1. Get the cutoff from the database (see below).  Nothing before this matters for this call to `send_slips_mail()`.
1. **Gather the raw data from the database:**
    1. Gather all regions that haven't launched yet *(their `date` attribute is in the future).*
    1. Gather all current service metadata records *(like `athena:v0`)*.
    1. Gather all current service plan records *(like `athena:v0:GRU`)*.
1. **Assemble `services`**, a large data structure that holds all the data above, all organized by the service's RIP short name:
    1. Store the service metadata object in `metadata`
    1. Store all service plan objects under the service metadata object in `regions`
    1. Store the regions that don't have a service plan for this service metadata in `noplan`
    1. A special flag denoting if there are `note` values for use in the MM email (in `has_notes`)*
1. **Business Logic:**
    1. Remove all service plans from `'regions'` for regions that haven't launched yet.  We don't track parity slips for unlaunched regions.
    1. For every service plan that was changed since we last ran `send_slips_mail()` *(see "cutoff" below)*, get it's previous value from the database and store in `'regions'`
    1. Gather all regions that each service **doesn't** have a plan for *(missing service plan in the database)* and store in `noplan`.
    1. Store `True` in `has_notes` if there is at least one region that:
        * Doesn't have a valid plan: it **can** have an entry in `regions`, though!  An entry in `regions` that doesn't have certain attributes can mean there isn't a plan for this region yet.
        * Does have a `note` attribute explaining something about the status of this service in this region.
1. **Compute Slips and Improvements:**
    1. For every service, for every plan in `regions`, get the `date` from the current plan and the previous plan retrieved above.
    1. Subtract: this is the difference in the last change: the number of days the delivery date was pushed out or moved closer.
    1. If it was pushed out, add it to the `slips` list, else add it to the `improvements` list.
    1. To avoid too much "chaff" in the final MM email messages, any slip or improvement of less than a month is ignored *(see `SLIP_DELTA` constant)*.
1. **Send to MessageMultiplexer:**
    1. Assemble the full message body to MM, using `slips` and `improvements` above *(plus a few other values)*.
    1. Call the MM API *(if we're not a dryrun execution)*.
    1. Send metrics to CloudWatch Metrics.


### A Note on Regions

There are many regions, and there is no sense clogging up the final MM email messages with more than needed, especially for regions that no service has a plan for.  This is a quirk of the logic in `send_slips_mail()`: all the business logic has double-loops over all services, and then all regions for each service.  As a way to reduce, the inner-loops do not loop over all launched regions.  The inner loops loop over only those launched regions that the `services` `regions` have entries for.  Put more clearly, don't bother with any launched region that isn't in `services.regions`.

This is implemented via `gather_unique_regions()`: it loops over `services` and collects all mentioned regions.



## Cutoff

Each time this is run from AWS Lambda function, it should pick-up from where it last left-off.  If it runs weekly, it should only use data in the last week.  If it has a problem running on it's normal schedule, the next execution should Do The Right Thing.  The Right Thing is to remember where it left off from the last successful execution.   This "I left off at ____" fact is stored in the `buildables` table with artifact=NOTIFICATION and instance=region-slips.  `send_slips_mail()` calls the DAO to retrieve and update this at the beginning and end of execution.




## Metrics

`message_send_success` set to 1 if there are no unhandled exceptions in the entire execution, 0 otherwise.

`message_send_failure` set to 1 if there is an unhandled exception, 0 otherwise.

`message_send_success` and `message_send_failure` are opposites of each other.

`slips_count` is the number of services that slipped for this run.

`improvements_count` is the number of services that improved for this run.



## "services" structure

Function `build_services()` creates this structure's basic layout, and many other functions read from, and modify it throughout execution of `send_slips_email()`.  This is **the** data structure that all business logic operates on.  It is populated initially from raw queries from the database, and modified by many functions along the way.  The `slips` and `improvements` structures that are sent to MessageMultiplexer are calculated directly from this data.

Overall, it's a map from a service's RIP name to a structure.  The structure holds all the data for one Service.  Each structure has all regions where the service **has** a plan (`regions`) along with all regions where the service **doesn't** have a plan (`noplan`).  This is the basic structure of the whole logic.

Here is an abbreviated sample generated from the test data in `slips_email_e2e_db.yaml`:

```
{
    'chrisjen': {
        'has_notes': False,
        'noplan': [],
        'metadata': {
            '0': {
                'artifact': 'SERVICE',
                'instance': 'chrisjen:v0',
                'name_pretty': 'chrisjen',
                'plan': 'myplan',
                'rip_name': 'chrisjen',
                'version_instance': Decimal('0')
            }
        },
        'regions': {
            'ABC': {
                '0': {
                    'artifact': 'SERVICE',
                    'belongs_to_artifact': 'REGION',
                    'belongs_to_instance': 'ABC',
                    'date': FakeDatetime(2020, 4, 26, 0, 0, tzinfo=<UTC>),
                    'instance': 'chrisjen:v0:ABC',
                    'plan': 'myplan',
                    'rip_name': 'chrisjen',
                    'updated': FakeDatetime(2020, 4, 26, 0, 0, tzinfo=<UTC>),
                    'updater': 'john',
                    'version_instance': Decimal('0'),
                    'version_latest': Decimal('2')},
                '1': {
                    'artifact': 'SERVICE',
                    'belongs_to_artifact': 'REGION',
                    'belongs_to_instance': 'ABC',
                    'date': FakeDatetime(2020, 2, 1, 0, 0, tzinfo=<UTC>),
                    'instance': 'chrisjen:v1:ABC',
                    'plan': 'myplan',
                    'rip_name': 'chrisjen',
                    'updated': FakeDatetime(2020, 4, 10, 0, 0, tzinfo=<UTC>),
                    'updater': 'chris',
                    'version_instance': Decimal('1'),
                    'version_latest': Decimal('2')
                }
            },
            'DEF': {
               '0': {
                    'artifact': 'SERVICE',
                    'belongs_to_artifact': 'REGION',
                    'belongs_to_instance': 'DEF',
                    'date': FakeDatetime(2020, 3, 10, 0, 0, tzinfo=<UTC>),
                    'instance': 'chrisjen:v0:DEF',
                    'plan': 'myplan',
                    'rip_name': 'chrisjen',
                    'updated': FakeDatetime(2020, 4, 26, 0, 0, tzinfo=<UTC>),
                    'updater': 'moe',
                    'version_instance': Decimal('0'),
                    'version_latest': Decimal('6')
                }
            }
        }
    },
    'klaes': {
        ...
    }
```



## Final parameters sent to MessageMultiplexer

For general referece, here is a sample structure sent to MM based on test data in `slips_email_e2e_db.yaml`:

```
{
    'beginning': '2020-04-21',
    'end': '2020-05-01',
    'improvement_count': 1,
    'improvements': [
        {
            'change': 33,
            'current': '2020-03-10',
            'name_pretty': 'chrisjen',
            'name_rip': 'chrisjen',
            'note': '',
            'previous': '2020-04-12',
            'region': 'DEF',
            'updated': '2020-04-26',
            'updater': 'moe'
        }
    ],
    'improvements_exist': True,
    'last_sent_date': '2020-04-21 04:05 UTC',
    'slip_count': 1,
    'slip_delta': 30,
    'slips': [
        {
            'change': 85,
            'current': '2020-04-26',
            'name_pretty': 'chrisjen',
            'name_rip': 'chrisjen',
            'note': '',
            'previous': '2020-02-01',
            'region': 'ABC',
            'updated': '2020-04-26',
            'updater': 'john'
        }
    ],
    'slips_exist': True,
    'unplanned': [
        {
            'has_notes': False,
            'name_pretty': 'klaes',
            'name_rip': 'klaes',
            'regions': [
                {'region': 'ABC', 'separator': ','},
                {'region': 'DEF', 'separator': ''}
            ]
        },
        {
            'has_notes': False,
            'name_pretty': 'sadavir',
            'name_rip': 'sadavir',
            'regions': [
                {'region': 'ABC', 'separator': ','},
                {'region': 'DEF', 'separator': ''}
            ]
        }
    ],
    'unplanned_count': 2
}
```
