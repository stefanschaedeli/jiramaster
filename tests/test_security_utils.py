from security_utils import (
    mask_token,
    mask_email,
    mask_url,
    mask_headers,
    mask_payload,
    sanitize_request,
    sanitize_response,
)


# ---------------------------------------------------------------------------
# mask_token
# ---------------------------------------------------------------------------

def test_mask_token_normal():
    assert mask_token("abcdef12345") == "abcd****"


def test_mask_token_short():
    assert mask_token("abc") == "****"
    assert mask_token("abcd") == "****"


def test_mask_token_empty():
    assert mask_token("") == ""


# ---------------------------------------------------------------------------
# mask_email
# ---------------------------------------------------------------------------

def test_mask_email_normal():
    assert mask_email("stefan@example.com") == "s***@example.com"


def test_mask_email_no_at():
    assert mask_email("noemail") == "****"


def test_mask_email_empty():
    assert mask_email("") == "****"


# ---------------------------------------------------------------------------
# mask_url
# ---------------------------------------------------------------------------

def test_mask_url_no_query():
    url = "https://example.atlassian.net/rest/api/3/issue"
    assert mask_url(url) == url


def test_mask_url_sensitive_param():
    url = "https://example.com/api?api_token=supersecret&page=1"
    result = mask_url(url)
    assert "supersecret" not in result
    assert "api_token=" in result  # key preserved; value masked (may be percent-encoded)
    assert "page=1" in result


def test_mask_url_safe_param():
    url = "https://example.com/api?page=2&limit=10"
    result = mask_url(url)
    assert "page=2" in result
    assert "limit=10" in result


# ---------------------------------------------------------------------------
# mask_headers
# ---------------------------------------------------------------------------

def test_mask_headers_sensitive():
    headers = {
        "Authorization": "Basic abc123",
        "Cookie": "session=xyz",
        "Content-Type": "application/json",
    }
    result = mask_headers(headers)
    assert result["Authorization"] == "****"
    assert result["Cookie"] == "****"
    assert result["Content-Type"] == "application/json"


def test_mask_headers_safe():
    headers = {"Accept": "application/json", "X-Request-ID": "123"}
    result = mask_headers(headers)
    assert result == headers


def test_mask_headers_empty():
    assert mask_headers({}) == {}


# ---------------------------------------------------------------------------
# mask_payload
# ---------------------------------------------------------------------------

def test_mask_payload_nested():
    payload = {
        "username": "alice",
        "credentials": {"password": "secret", "token": "tok123"},
        "data": {"value": 42},
    }
    result = mask_payload(payload)
    assert result["username"] == "alice"
    assert result["credentials"] == "****"
    assert result["data"]["value"] == 42


def test_mask_payload_depth_limit():
    # Build a deeply nested structure beyond depth 10
    deep = "leaf"
    for _ in range(12):
        deep = {"nested": deep}
    result = mask_payload(deep)
    # At depth > 10, returns "..."
    assert "..." in str(result)


def test_mask_payload_list():
    payload = [{"token": "abc"}, {"safe": "value"}]
    result = mask_payload(payload)
    assert result[0]["token"] == "****"
    assert result[1]["safe"] == "value"


# ---------------------------------------------------------------------------
# sanitize_request / sanitize_response
# ---------------------------------------------------------------------------

def test_sanitize_request_combines_masks():
    result = sanitize_request(
        method="get",
        url="https://example.com/api?api_token=secret",
        headers={"Authorization": "Basic abc"},
        body={"password": "hunter2"},
    )
    assert result["method"] == "GET"
    assert "secret" not in result["url"]
    assert result["headers"]["Authorization"] == "****"
    assert result["body"]["password"] == "****"


def test_sanitize_response_truncates_string_body():
    long_body = "x" * 1000
    result = sanitize_response(200, body=long_body)
    assert len(result["body"]) == 500


def test_sanitize_response_masks_dict_body():
    result = sanitize_response(200, body={"token": "secret", "ok": True})
    assert result["body"]["token"] == "****"
    assert result["body"]["ok"] is True


def test_sanitize_response_no_body():
    result = sanitize_response(404)
    assert result["status"] == 404
    assert "body" not in result


def test_sanitize_response_with_summary():
    result = sanitize_response(200, summary="Created issue")
    assert result["summary"] == "Created issue"
