import json

def safeget(dct, keys, validate=False):
    for key in keys.split('.'):
        if key in dct:
            dct = dct[key]
        else:
            dct = None
            break

    if validate and dct is None:
        raise ValueError(f"Input records need a {keys} value")

    return dct


class RipMessageRecord():
    def __init__(self, raw_json_record):
        body = safeget(raw_json_record, 'body', validate=True)
        if isinstance(body, str):
            body = json.loads(body)

        self.message = safeget(body, 'Message', validate=True)
        if isinstance(self.message, str):
            self.message = json.loads(self.message)

        self.change_type    = safeget(body, 'MessageAttributes.changeType.Value')
        self.receipt_handle = safeget(raw_json_record, 'receiptHandle')

        self.rip_name       = safeget(self.message, 'dimension.name')
        self.status         = safeget(self.message, 'status')
