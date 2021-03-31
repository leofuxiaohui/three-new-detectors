import boto3

class DynamoQuery():
    def __init__(self, table_name):
        self.table_name = table_name
        ddb = boto3.resource('dynamodb', region_name='us-east-1')
        self.table = ddb.Table(table_name)


    def query(self, key_condition, project_fields=None, index_name=None, filter=None):
        query_params = dict(KeyConditionExpression=key_condition)
        self._add_project_fields_to_dict(query_params, project_fields)

        if index_name:
            query_params['IndexName'] = index_name

        if filter:
            query_params['FilterExpression'] = filter

        items = []
        while True:
            response = self.table.query(**query_params)
            items.extend(response[u'Items'])

            try:
                query_params["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            except KeyError:
                break
        return items


    def get_item(self, artifact, instance, project_fields=None):
        query_params = {
            'Key': {
                'artifact': artifact,
                'instance': instance
            }
        }
        self._add_project_fields_to_dict(query_params, project_fields)
        response = self.table.get_item(**query_params)
        return response.get('Item')


    def update_item(self, artifact, instance, **kwargs):
        update_parts = [ 'SET {}=:{}'.format(key, key)  for key in kwargs ]
        expr_parts   = { ':{}'.format(key): val  for key,val in kwargs.items() }
        params = {
            'Key': {
                'artifact': artifact,
                'instance': instance
            },
            'UpdateExpression': ', '.join(update_parts),
            'ExpressionAttributeValues': expr_parts
        }
        self.table.update_item(**params)


    def _add_project_fields_to_dict(self, dict, project_fields):
        if project_fields:
            project_names = [ '#{}'.format(field_name) for field_name in project_fields ] # convert [ 'a', 'b' ] into [ '#a', '#b' ]
            project_names_str = ", ".join(project_names)
            project_names_dict = { '#{}'.format(field_name): field_name for field_name in project_fields } # convert [ 'a', 'b' ] into { '#a': 'a', '#b': 'b' }
            dict['ProjectionExpression'] = project_names_str
            dict['ExpressionAttributeNames'] = project_names_dict
