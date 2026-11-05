from dataclasses import dataclass, field


class ProviderError(Exception):
    """Provider is unreachable or returned an unusable answer. Retry later."""


@dataclass
class Checkout:
    reference: str
    url: str


@dataclass
class Verification:
    status: str  # "SUCCESSFUL", "FAILED", "PENDING", "NOT_FOUND"
    amount: object = None
    currency: str = ""
    raw: dict = field(default_factory=dict)


class ProviderAdapter:
    name = ""

    def create_checkout(self, payment, user, plan, redirect_url) -> Checkout:
        raise NotImplementedError

    def verify(self, payment) -> Verification:
        raise NotImplementedError
