#!/usr/bin/env python3
"""A local stand-in for Clerk, so CI can exercise the real auth path.

The backend verifies RS256 session tokens against a JWKS it fetches from
CLERK_ISSUER, then calls the Clerk Backend API to look up a new user's email
on first sign-in. Neither of those can point at real Clerk in CI without
putting live credentials in the workflow.

The alternative would have been an auth bypass flag in get_current_user —
deliberately not done. A test-only branch that skips signature verification is
exactly the kind of thing that survives into production. Instead this serves a
real JWKS backed by a real keypair, and mints real signatures, so the code
under test does genuine cryptographic verification against genuine keys. The
only thing that is fake is which server the keys came from.

The keypair is generated fresh on every boot and never written to disk, so
there is no private key committed to this repo.

Endpoints
    GET  /.well-known/jwks.json     public signing key (what CLERK_ISSUER serves)
    GET  /v1/users/{id}             Clerk Backend API user lookup
    POST /__test__/token            mint a session token (test-only)
    GET  /health                    readiness

Run:
    python tests/clerk_stub.py --port 8799
"""
from __future__ import annotations

import argparse
import base64
import json
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

KEY_ID = "ijt-test-key-1"

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_private_pem = _private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)

# Users this stub has minted tokens for, keyed by Clerk user id. GET
# /v1/users/{id} reads from here, mirroring the shape clerk_auth's
# _primary_email() and _display_name() expect.
_users: dict[str, dict] = {}


def _b64u_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _jwks() -> dict:
    numbers = _private_key.public_key().public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": KEY_ID,
                "n": _b64u_uint(numbers.n),
                "e": _b64u_uint(numbers.e),
            }
        ]
    }


def mint_token(issuer: str, email: str, name: str = "", ttl: int = 3600,
               fva_minutes: int = 0) -> dict:
    """Create a signed session token and register the matching user."""
    clerk_id = f"user_{uuid.uuid4().hex[:24]}"
    first, _, last = name.partition(" ")

    _users[clerk_id] = {
        "id": clerk_id,
        "first_name": first,
        "last_name": last,
        "username": None,
        "primary_email_address_id": "idn_primary",
        "email_addresses": [
            {"id": "idn_primary", "email_address": email},
        ],
        "public_metadata": {},
    }

    now = int(time.time())
    claims = {
        "sub": clerk_id,
        "iss": issuer,
        "iat": now,
        "nbf": now,
        "exp": now + ttl,
        "sid": f"sess_{uuid.uuid4().hex[:24]}",
        # Factor verification age, [first_factor, second_factor] in minutes.
        # rbac.verify_step_up reads this; -1 means "never verified".
        "fva": [fva_minutes, -1],
    }
    token = jwt.encode(
        claims, _private_pem, algorithm="RS256", headers={"kid": KEY_ID}
    )
    return {"token": token, "clerk_id": clerk_id, "email": email}


class Handler(BaseHTTPRequestHandler):
    server_version = "ClerkStub/1.0"

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 (stdlib naming)
        if self.path == "/health":
            return self._send(200, {"ok": True})
        if self.path == "/.well-known/jwks.json":
            return self._send(200, _jwks())
        if self.path.startswith("/v1/users/"):
            clerk_id = self.path.rsplit("/", 1)[-1]
            user = _users.get(clerk_id)
            if not user:
                return self._send(404, {"errors": [{"message": "not found"}]})
            return self._send(200, user)
        return self._send(404, {"errors": [{"message": "no such route"}]})

    def do_POST(self):  # noqa: N802
        if self.path != "/__test__/token":
            return self._send(404, {"errors": [{"message": "no such route"}]})
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        result = mint_token(
            issuer=self.server.issuer,
            email=body.get("email") or f"test-{uuid.uuid4().hex[:8]}@example.com",
            name=body.get("name", "Test User"),
            fva_minutes=body.get("fva_minutes", 0),
        )
        return self._send(200, result)

    def log_message(self, *args):
        pass  # keep CI logs readable


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8799)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), Handler)
    # The issuer the backend is configured with must match the `iss` we sign,
    # or PyJWT rejects the token — which is the point of testing this way.
    server.issuer = f"http://{args.host}:{args.port}"
    print(f"clerk stub listening on {server.issuer}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
