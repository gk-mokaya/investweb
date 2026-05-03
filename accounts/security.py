from hashlib import sha256


def build_browser_fingerprint(request) -> str:
    """
    Build a browser-centric fingerprint from request headers.

    This is intentionally stricter than a normal session cookie: if the same
    session is reused from a different browser profile, the header mix should
    change and the session will be invalidated.
    """
    headers = request.headers
    parts = [
        headers.get('User-Agent', ''),
        headers.get('Accept', ''),
        headers.get('Accept-Language', ''),
        headers.get('Accept-Encoding', ''),
        headers.get('Sec-CH-UA', ''),
        headers.get('Sec-CH-UA-Mobile', ''),
        headers.get('Sec-CH-UA-Platform', ''),
    ]
    payload = '|'.join(part.strip() for part in parts)
    return sha256(payload.encode('utf-8')).hexdigest()
