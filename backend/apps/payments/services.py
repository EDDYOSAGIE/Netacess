import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.access_codes.services import issue_code
from apps.notifications.services import notify
from apps.orders.models import Order
from apps.plans.models import Subscription

from .models import Payment, PaymentEvent
from .providers import breaker, get_adapter
from .providers.base import ProviderError, Verification

ALLOWED = {
    Payment.INITIATED: {Payment.PENDING, Payment.FAILED, Payment.EXPIRED},
    Payment.PENDING: {Payment.SUCCESSFUL, Payment.FAILED, Payment.EXPIRED, Payment.NEEDS_REVIEW},
    # A late success must still be honoured, so FAILED and EXPIRED can become SUCCESSFUL
    Payment.FAILED: {Payment.SUCCESSFUL, Payment.NEEDS_REVIEW},
    Payment.EXPIRED: {Payment.SUCCESSFUL, Payment.NEEDS_REVIEW},
    Payment.NEEDS_REVIEW: {Payment.SUCCESSFUL, Payment.FAILED, Payment.REFUNDED},
    Payment.SUCCESSFUL: {Payment.REFUNDED},
    Payment.REFUNDED: set(),
}


def log_event(payment, source, event_type, payload=None, event_id=""):
    """Returns False when this exact provider event was already recorded."""
    try:
        with transaction.atomic():
            PaymentEvent.objects.create(payment=payment, source=source, event_type=event_type,
                                        event_id=event_id, payload=payload or {})
        return True
    except IntegrityError:
        return False


def _move(payment, new_status):
    if new_status == payment.status:
        return False
    if new_status not in ALLOWED[payment.status]:
        return False
    payment.status = new_status
    payment.save(update_fields=["status", "updated_at"])
    return True


def initiate_payment(user, plan, provider, idempotency_key):
    """Creates an order and a payment, then asks the provider for a checkout link.
    The same idempotency key returns the same order, so a double tap never double-charges."""
    esp = provider == Order.ESPEES
    order, created = Order.objects.get_or_create(
        user=user, idempotency_key=idempotency_key,
        defaults={"plan": plan, "provider": provider,
                  "amount_ngn_kobo": None if esp else plan.price_ngn_kobo,
                  "amount_esp": plan.price_esp if esp else None})
    if not created:
        payment = order.payments.order_by("-created_at").first()
        # Same key returns the live attempt (never a second charge), but a failed or expired
        # attempt must not block the customer from trying again.
        if payment and payment.status in (Payment.INITIATED, Payment.PENDING, Payment.SUCCESSFUL,
                                          Payment.NEEDS_REVIEW):
            return order, payment
        if order.status in (Order.FAILED, Order.EXPIRED):
            order.status = Order.PENDING
            order.save(update_fields=["status"])
    from apps.adminops.providers import is_enabled
    if not is_enabled(provider):
        raise ProviderError(f"{provider} is switched off")
    if breaker.is_open(provider):
        raise ProviderError(f"{provider} is temporarily unavailable")
    pid = uuid.uuid4()
    payment = Payment.objects.create(
        id=pid, order=order, provider=provider,
        provider_reference=f"NA-{pid.hex}" if not esp else f"pending-{pid.hex}",
        amount=plan.price_esp if esp else Decimal(plan.price_ngn_kobo),
        currency="ESP" if esp else "NGN",
        expires_at=timezone.now() + timedelta(minutes=settings.PAYMENT_PENDING_EXPIRY_MINUTES))
    redirect = f"{settings.FRONTEND_URL}/payment/{payment.id}"
    try:
        checkout = get_adapter(provider).create_checkout(payment, user, plan, redirect)
    except ProviderError as e:
        breaker.record_failure(provider)
        if breaker.is_open(provider) and cache.add(f"alerted:{provider}", 1, 600):
            _send_alert(f"{provider.title()} is failing at checkout",
                        f"{provider.title()} checkout has failed repeatedly. Customers are being told to use the other method. "
                        "You can switch it off from the Payment providers card.", "/admin", f"provider:{provider}")
        log_event(payment, "system", "checkout_failed", {"error": str(e)})
        _move(payment, Payment.FAILED)
        raise
    breaker.reset(provider)
    payment.provider_reference = checkout.reference
    payment.checkout_url = checkout.url
    payment.save(update_fields=["provider_reference", "checkout_url", "updated_at"])
    _move(payment, Payment.PENDING)
    log_event(payment, "system", "checkout_created", {"url": checkout.url})
    return order, payment


def _alert_review(payment, v):
    """Tell staff. Sent after the database commit, so a rolled-back change never alerts."""
    kind = "currency" if v.currency and v.currency != payment.currency else "amount"
    path = f"/admin/payments/{payment.id}"
    pid = str(payment.id)
    transaction.on_commit(lambda: _send_alert(
        f"Payment needs review: {kind} mismatch",
        f"A {payment.provider} payment for {payment.order.plan.name} was paid with a different {kind} than expected. "
        f"No access code was issued. Check the provider dashboard, then approve or refund.",
        path, f"review:{pid}"))


def _send_alert(title, body, path, dedupe):
    try:
        from apps.adminops.tasks import send_alert
        send_alert.delay(title, body, path, dedupe)
    except Exception:  # a broken queue must never affect payments; the hourly reminder is the backstop
        import logging  
        logging.getLogger(__name__).exception("could not queue staff alert")


def _amount_matches(payment, v):
    if v.amount is None:
        return True
    return Decimal(str(v.amount)) == Decimal(payment.amount) and (not v.currency or v.currency == payment.currency)


def _safe_verification_payload(payload):
    sensitive = {"token", "authorization", "card_number", "cvv", "expiry", "first_6digits"}
    if isinstance(payload, dict):
        return {key: _safe_verification_payload(value) for key, value in payload.items() if key.lower() not in sensitive}
    if isinstance(payload, list):
        return [_safe_verification_payload(value) for value in payload]
    return payload


@transaction.atomic
def apply_verification(payment_id, v: Verification, source, event_id=""):
    """Single place where provider results change a payment. Safe to call many times."""
    payment = Payment.objects.select_for_update().select_related("order__plan", "order__user").get(pk=payment_id)
    # Background re-checks that change nothing are not logged, so the event table stays small
    quiet = source == "poll" and not (
        (v.status == "SUCCESSFUL" and payment.status != Payment.SUCCESSFUL)
        or (v.status == "FAILED" and payment.status != Payment.FAILED))
    if not quiet:
        log_event(payment, source, f"verify_{v.status.lower()}", _safe_verification_payload(v.raw), event_id)
    payment.last_checked_at = timezone.now()
    payment.save(update_fields=["last_checked_at"])
    order, user = payment.order, payment.order.user

    if v.status == "SUCCESSFUL":
        if payment.status == Payment.SUCCESSFUL:
            return payment  # already done, nothing to repeat
        if not _amount_matches(payment, v):
            if _move(payment, Payment.NEEDS_REVIEW):
                log_event(payment, "system", "amount_mismatch",
                          {"expected": str(payment.amount), "got": str(v.amount), "currency": v.currency})
                _alert_review(payment, v)
            return payment
        if payment.provider == "flutterwave" and v.raw.get("payment_type") == "card":
            card = v.raw.get("card") or {}
            last4 = str(card.get("last_4digits") or "")
            if len(last4) == 4 and last4.isdigit():
                payment.card_brand = str(card.get("type") or card.get("issuer") or "")[:32]
                payment.card_last4 = last4
                payment.save(update_fields=["card_brand", "card_last4", "updated_at"])
        if _move(payment, Payment.SUCCESSFUL):
            _fulfil(payment, order, user)
    elif v.status == "FAILED":
        if _move(payment, Payment.FAILED):
            order.status = Order.FAILED
            order.save(update_fields=["status"])
            notify(user, "payment_failed", "Payment failed",
                   "Your payment did not go through. You were not charged, or any charge will be reversed.",
                   dedupe_key=f"failed:{payment.id}")
    elif v.status == "PENDING" and payment.status == Payment.INITIATED:
        _move(payment, Payment.PENDING)
    return payment


def _fulfil(payment, order, user, send_access_sms=True):
    plan = order.plan
    now = timezone.now()
    current = (Subscription.objects.filter(user=user, status=Subscription.ACTIVE, expires_at__gt=now)
               .order_by("-expires_at").first())
    start = current.expires_at if current else now  # renewing extends, never overlaps
    sub = Subscription.objects.create(user=user, plan=plan, starts_at=start,
                                      expires_at=start + timedelta(days=plan.duration_days))
    order.status = Order.PAID
    order.save(update_fields=["status"])
    access_code = issue_code(payment, sub)  # the flow ends here: a valid code exists
    if send_access_sms:
        from apps.access_codes.services import decrypt
        sms_message = f"Your Netacess access code is {decrypt(access_code)}. Your plan expires on {sub.expires_at:%b %d, %Y}."
        reference = f"access-{payment.provider_reference}"
        transaction.on_commit(lambda: _queue_access_code_sms(user.phone, sms_message, reference))
    amount = f"₦{int(payment.amount) // 100:,}" if payment.currency == "NGN" else f"{payment.amount.normalize()} ESP"
    notify(user, "payment_received", "Payment received", f"We received your payment of {amount}.",
           dedupe_key=f"paid:{payment.id}")
    notify(user, "code_issued", "Access code issued", "Your Netacess access code is ready.",
           dedupe_key=f"code:{payment.id}")


def _queue_access_code_sms(phone, message, reference):
    try:
        from apps.sms.tasks import send_sms_task
        send_sms_task.delay(phone, message, "access_code", reference)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("could not queue access-code SMS reference %s", reference)


def check_payment(payment_id, source="poll"):
    """Ask the provider for the truth and apply it."""
    payment = Payment.objects.get(pk=payment_id)
    v = get_adapter(payment.provider).verify(payment)
    return apply_verification(payment.id, v, source)


def expire_stale(payment):
    if payment.status in (Payment.INITIATED, Payment.PENDING) and payment.expires_at and payment.expires_at < timezone.now():
        with transaction.atomic():
            p = Payment.objects.select_for_update().get(pk=payment.pk)
            if _move(p, Payment.EXPIRED):
                p.order.status = Order.EXPIRED
                p.order.save(update_fields=["status"])
                log_event(p, "system", "expired")


@transaction.atomic
def admin_approve(payment_id, staff_user, reason=""):
    """Staff confirms they really received the money (after checking the provider dashboard).
    Issues the code through the same path as an automatic success."""
    payment = Payment.objects.select_for_update().select_related("order__plan", "order__user").get(pk=payment_id)
    if payment.status == Payment.SUCCESSFUL:
        return payment
    if payment.status not in (Payment.NEEDS_REVIEW, Payment.FAILED, Payment.EXPIRED, Payment.PENDING):
        raise ValueError(f"Cannot approve a payment that is {payment.status}")
    payment.status = Payment.SUCCESSFUL
    payment.save(update_fields=["status", "updated_at"])
    log_event(payment, "admin", "approved", {"by": str(staff_user.pk), "reason": reason})
    _fulfil(payment, payment.order, payment.order.user, send_access_sms=False)
    return payment


@transaction.atomic
def admin_mark(payment_id, new_status, staff_user, reason=""):
    payment = Payment.objects.select_for_update().get(pk=payment_id)
    if new_status not in (Payment.FAILED, Payment.REFUNDED) or not _move(payment, new_status):
        raise ValueError(f"Cannot move {payment.status} to {new_status}")
    log_event(payment, "admin", f"marked_{new_status.lower()}", {"by": str(staff_user.pk), "reason": reason})
    return payment
