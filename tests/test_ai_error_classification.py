"""AI error classification and diagnostics.

The openai SDK often leaves body=None on APIStatusError, so the real payload only
exists in error.response. Reading error.body alone drops the local proxy payload
(model_not_found, upstream error, ...) and the user sees a vague message.
"""

from __future__ import annotations

import httpx
import pytest
from openai import APIConnectionError, BadRequestError, InternalServerError, NotFoundError

from src.platform.ai.errors import (
    classify_ai_service_error,
    diagnostic_ai_error_message,
)


def _response(status, payload=None, text=None):
    request = httpx.Request("POST", "http://host.docker.internal:7897/v1/chat/completions")
    if payload is not None:
        return httpx.Response(status, request=request, json=payload)
    return httpx.Response(status, request=request, text=text or "")


def _status_error(cls, status, payload=None, text=None, body=None):
    """Mirror the SDK: without an explicit body, error.body is None and the
    payload only lives in the response object."""
    return cls("provider error", response=_response(status, payload, text), body=body)


class TestClassifyFromResponsePayload:
    """Classification must see the response payload, otherwise every 5xx
    is reported as an unreadable service_unavailable."""

    def test_model_not_found_in_body_is_classified_as_model_unavailable(self):
        error = _status_error(InternalServerError, 500, {
            "error": {"code": "model_not_found",
                      "message": "model deepseek-v4.1-flash not available"}
        })
        assert classify_ai_service_error(error).code == "ai_model_unavailable"

    def test_invalid_api_key_in_body_is_classified_as_auth_failed(self):
        error = _status_error(InternalServerError, 500, {
            "error": {"code": "invalid_api_key",
                      "message": "Invalid API key"}
        })
        assert classify_ai_service_error(error).code == "ai_authentication_failed"

    def test_insufficient_quota_in_body_is_classified_as_quota(self):
        error = _status_error(InternalServerError, 500, {
            "error": {"message": "insufficient_quota"}
        })
        assert classify_ai_service_error(error).code == "ai_quota_exhausted"

    def test_plain_500_without_payload_stays_service_unavailable(self):
        error = _status_error(InternalServerError, 500, text="Internal Server Error")
        assert classify_ai_service_error(error).code == "ai_service_unavailable"

class TestDiagnosticMessage:
    """The diagnostic must carry provider detail, otherwise there is nothing
    to act on when a run fails."""

    def test_includes_provider_code_and_message(self):
        error = _status_error(InternalServerError, 500, {
            "error": {"code": "model_not_found",
                      "message": "model deepseek-v4.1-flash not available"}
        })
        message = diagnostic_ai_error_message(error)
        assert "model_not_found" in message
        assert "deepseek-v4.1-flash" in message

    def test_404_model_not_found_is_reported(self):
        error = _status_error(NotFoundError, 404, {
            "error": {"code": "model_not_found", "message": "no such model"}
        })
        assert classify_ai_service_error(error).code == "ai_model_unavailable"
        assert "model_not_found" in diagnostic_ai_error_message(error)

    def test_connection_error_still_reports_connection_failed(self):
        assert classify_ai_service_error(APIConnectionError(request=None)).code == "ai_connection_failed"

    def test_400_bad_request_is_not_masked_as_service_unavailable(self):
        error = _status_error(BadRequestError, 400, {
            "error": {"code": "context_length_exceeded",
                      "message": "too many tokens"}
        })
        assert classify_ai_service_error(error).code == "ai_context_limit_exceeded"

    def test_secrets_are_redacted_in_diagnostic(self):
        error = _status_error(InternalServerError, 500, {
            "error": {"message": "authorization: Bearer sk-abcdef123456"}
        })
        assert "sk-abcdef123456" not in diagnostic_ai_error_message(error)
