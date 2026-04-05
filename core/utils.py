import json


def dictionary_to_json(dictionary):
    json_dump = json.dumps(dictionary)
    json_transform = json_dump.replace("'", "''")
    return json_transform

def exclude_columns_from_dataframe (dataframe, columns_to_exclude):
    if dataframe is None:
        return None

    if columns_to_exclude is None or len(columns_to_exclude) == 0:
        return dataframe

    dataframe_type = type(dataframe).__name__
    dataframe_to_convert = dataframe.copy()

    if dataframe_type == 'DataFrame':
        return dataframe_to_convert.drop(columns=columns_to_exclude)

    # Styler
    return dataframe_to_convert.hide_columns(columns_to_exclude)