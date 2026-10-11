"""REL-V1: the dependencies APNs push delivery needs must be installed.

httpx.AsyncClient(http2=True) raises ImportError without the h2 package, and
ES256 provider-token signing needs cryptography. Both come from extras in
requirements.txt (httpx[http2], PyJWT[crypto]).
"""
import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def test_httpx_http2_available():
    httpx.Client(http2=True).close()


def test_pyjwt_es256_available():
    pem = ec.generate_private_key(ec.SECP256R1()).private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    token = jwt.encode({"iss": "T", "iat": 0}, pem, algorithm="ES256", headers={"kid": "K"})
    assert isinstance(token, str)
    assert jwt.get_unverified_header(token)["kid"] == "K"
