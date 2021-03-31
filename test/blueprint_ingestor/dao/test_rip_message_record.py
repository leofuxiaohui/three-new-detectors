import pytest
from regions_recon_lambda.rip_message_record import RipMessageRecord


def test_empty_json():
    with pytest.raises(ValueError, match=r"need a body"):
        RipMessageRecord({})


def test_empty_body():
    with pytest.raises(ValueError, match=r"need a Message"):
        RipMessageRecord({ "body": {} })


def test_empty_message():
    rmr = RipMessageRecord({ "body": { "Message": {} } })
    assert rmr.message == {}
    assert rmr.change_type is None
    assert rmr.rip_name is None


def test_full_object_message():
    rmr = RipMessageRecord({
        'body': {
            'Message': {
                'dimension': { 'name': 'myDim' },
                'receiptHandle': 'blahblahblah'
            },
            'MessageAttributes': { 'changeType' : { 'Value': 'myCT' } }
        }
    })
    assert rmr.message == { 'dimension': { 'name': 'myDim' }, 'receiptHandle': 'blahblahblah' }
    assert rmr.change_type == 'myCT'
    assert rmr.rip_name == 'myDim'


def test_full_string_message():
    rmr = RipMessageRecord({
        'body': {
            'Message': """
                {
                    "dimension": { "name": "myDim" },
                    "receiptHandle": "blahblahblah"
                }""",
            "MessageAttributes": { "changeType" : { "Value": "myCT" } }
        }
    })
    assert rmr.message == { 'dimension': { 'name': 'myDim' }, 'receiptHandle': 'blahblahblah' }
    assert rmr.change_type == 'myCT'
    assert rmr.rip_name == 'myDim'


def test_full_string_body():
    rmr = RipMessageRecord({
        "body": """
            {
                "Message": {
                    "dimension": { "name": "myDim" },
                    "receiptHandle": "blahblahblah"
                },
                "MessageAttributes": { "changeType" : { "Value": "myCT" } }
            }"""
    })
    assert rmr.message == { 'dimension': { 'name': 'myDim' }, 'receiptHandle': 'blahblahblah' }
    assert rmr.change_type == 'myCT'
    assert rmr.rip_name == 'myDim'
