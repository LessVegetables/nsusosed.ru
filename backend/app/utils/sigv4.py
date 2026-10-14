"""Подпись запросов AWS Signature Version 4.

Postbox (Amazon SES v2-совместимый API) принимает статический ключ доступа
сервисного аккаунта Yandex Cloud с подписью SigV4: сервис «ses», регион «ru-central1».
https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_sigv-create-signed-request.html
"""

from __future__ import annotations
import hashlib
import hmac
from datetime import datetime
from urllib.parse import quote, urlsplit


def _hmac(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def sign_headers(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes,
    *,
    access_key_id: str,
    secret_access_key: str,
    region: str,
    service: str,
    now: datetime,
) -> dict[str, str]:
    """
    Вернуть заголовки запроса с добавленными Host, X-Amz-Date и Authorization.
    Подписываются все переданные заголовки; тело отправлять ровно теми байтами, что в `body`.
    `now` — время в UTC. Запросы с query string не нужны и не поддерживаются.
    """
    parts = urlsplit(url)
    if parts.query:
        raise ValueError("query string is not supported")
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date = amz_date[:8]

    signed = {k.lower(): " ".join(v.split()) for k, v in headers.items()}
    signed["host"] = parts.netloc
    signed["x-amz-date"] = amz_date
    names = sorted(signed)
    signed_headers = ";".join(names)

    canonical_request = "\n".join([
        method.upper(),
        quote(parts.path or "/", safe="/-_.~"),
        "",  # query string
        "".join(f"{n}:{signed[n]}\n" for n in names),
        signed_headers,
        hashlib.sha256(body).hexdigest(),
    ])
    scope = f"{date}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256",
        amz_date,
        scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])

    key = _hmac(("AWS4" + secret_access_key).encode("utf-8"), date)
    key = _hmac(key, region)
    key = _hmac(key, service)
    key = _hmac(key, "aws4_request")
    signature = hmac.new(key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    return {
        **headers,
        "Host": parts.netloc,
        "X-Amz-Date": amz_date,
        "Authorization": (
            f"AWS4-HMAC-SHA256 Credential={access_key_id}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        ),
    }
