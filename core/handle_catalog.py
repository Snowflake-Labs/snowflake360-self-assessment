import json

CATALOG_PATH = 'core/data/catalog.json'


def load_catalog():
    try:
        with open(CATALOG_PATH, 'r') as file:
            catalog = json.load(file)
    except Exception as e:
        raise RuntimeError(f"Unexpected error while loading the account review catalog: {e}")
    return catalog
