from flypingavia.api.telegram_auth import build_test_init_data, validate_webapp_init_data


def test_webapp_init_data_roundtrip() -> None:
    token = "123456:TESTTOKEN"
    init_data = build_test_init_data(token, user_id=42, username="kirill")
    parsed = validate_webapp_init_data(init_data, token)
    assert parsed["user_id"] == 42
    assert parsed["username"] == "kirill"


def test_webapp_init_data_rejects_bad_hash() -> None:
    token = "123456:TESTTOKEN"
    init_data = build_test_init_data(token, user_id=1) + "tampered"
    try:
        validate_webapp_init_data(init_data, token)
        assert False, "should raise"
    except ValueError:
        pass
