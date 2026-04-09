from .finops_visibility import _ALL_VIS_QUERIES
from .finops_control import _ALL_CTRL_QUERIES
from .finops_optimization import _ALL_OPT_QUERIES

_ALL_FINOPS_QUERIES = {}
_ALL_FINOPS_QUERIES.update(_ALL_VIS_QUERIES)
_ALL_FINOPS_QUERIES.update(_ALL_CTRL_QUERIES)
_ALL_FINOPS_QUERIES.update(_ALL_OPT_QUERIES)
