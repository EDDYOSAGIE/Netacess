from .espees import EspeesAdapter
from .flutterwave import FlutterwaveAdapter

_ADAPTERS = {"flutterwave": FlutterwaveAdapter, "espees": EspeesAdapter}


def get_adapter(name):
    return _ADAPTERS[name]()
