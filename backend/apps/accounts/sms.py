def send_sms(phone, message):
    """Send staff alerts through the configured provider."""
    from apps.sms.providers import get_provider

    return get_provider().send(phone, message)
