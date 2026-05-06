import os
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker

from backend.app.main import app


client = TestClient(app)


def test_health_endpoint_returns_ok():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "spider-xhs"}


def test_platforms_endpoint_exposes_product_registry():
    response = client.get("/api/platforms")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 6
    assert payload["items"][0]["id"] == "xhs"
    assert payload["items"][0]["enabled"] is True
    assert payload["items"][1]["status"] == "coming_soon"


def test_xhs_analytics_overview_requires_authentication(tmp_path):
    db_dependency = _override_database(tmp_path)
    try:
        response = client.get("/api/xhs/analytics/overview")

        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_backend_foundation_modules_import():
    from backend.app.core.config import get_settings
    from backend.app.core.database import Base
    from backend.app.models import PlatformAccount, Note, Task, User

    settings = get_settings()
    assert settings.app_name == "Spider_XHS"
    assert Base is not None
    assert User.__tablename__ == "users"
    assert PlatformAccount.__tablename__ == "platform_accounts"
    assert Note.__tablename__ == "notes"
    assert Task.__tablename__ == "tasks"


def test_accounts_page_does_not_auto_check_accounts_on_load():
    source = open("frontend/src/pages/platforms/xhs/accounts-page.tsx", encoding="utf-8").read()

    assert "refreshMissingProfiles" not in source
    assert "void refreshMissingProfiles(loadedAccounts)" not in source


def test_accounts_page_uses_antd_components_and_shows_check_state():
    source = open("frontend/src/pages/platforms/xhs/accounts-page.tsx", encoding="utf-8").read()

    assert "antd" in source
    assert "checkingAccountIds" in source or "checkingId" in source or "isChecking" in source
    assert "检查" in source


def test_xhs_direct_request_env_temporarily_removes_proxy_variables(monkeypatch):
    from backend.app.adapters.xhs.request_env import PROXY_ENV_KEYS, direct_xhs_request_env

    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:10809")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:10809")

    with direct_xhs_request_env():
        assert all(key not in os.environ for key in PROXY_ENV_KEYS)

    assert os.environ["HTTPS_PROXY"] == "http://127.0.0.1:10809"
    assert os.environ["HTTP_PROXY"] == "http://127.0.0.1:10809"


def test_xhs_adapters_isolate_sdk_calls_from_broken_system_proxy():
    adapter_paths = [
        "backend/app/adapters/xhs/creator_login_adapter.py",
        "backend/app/adapters/xhs/creator_api_adapter.py",
        "backend/app/adapters/xhs/pc_login_adapter.py",
        "backend/app/adapters/xhs/pc_api_adapter.py",
    ]

    for path in adapter_paths:
        source = open(path, encoding="utf-8").read()
        assert "direct_xhs_request_env" in source


def test_crawler_page_exports_spider_style_excel():
    source = open("frontend/src/pages/platforms/xhs/crawler-page.tsx", encoding="utf-8").read()

    assert "noteExcelHeaders" in source
    assert "笔记id" in source
    assert "图片地址url列表" in source
    assert "application/vnd.ms-excel;charset=utf-8" in source


def test_crawler_page_uses_antd_table():
    source = open("frontend/src/pages/platforms/xhs/crawler-page.tsx", encoding="utf-8").read()

    assert "antd" in source
    assert "Table" in source


def test_discovery_uses_antd_components_and_preserves_core_logic():
    source = open("frontend/src/pages/platforms/xhs/discovery-page.tsx", encoding="utf-8").read()

    assert "antd" in source
    assert "async function ensureNoteDetail" in source or "ensureNoteDetail" in source
    assert "保存" in source
    assert "评论" in source
    assert "原文" in source


def test_discovery_preserves_note_detail_and_media_logic():
    source = open("frontend/src/pages/platforms/xhs/discovery-page.tsx", encoding="utf-8").read()

    assert "function getNoteVideoUrl" in source
    assert "function getNoteKindLabel" in source
    assert "detailMediaIndex" in source
    assert "视频" in source
    assert "图文" in source


def test_library_page_preserves_delete_and_media_logic():
    source = open("frontend/src/pages/platforms/xhs/library-page.tsx", encoding="utf-8").read()
    api_source = open("frontend/src/lib/api.ts", encoding="utf-8").read()

    assert "deleteSavedNote" in api_source
    assert "handleDeleteNote" in source
    assert "删除" in source
    assert "function getSavedNoteCoverUrl" in source
    assert 'referrerPolicy="no-referrer"' in source


def test_discovery_cards_show_note_media_type():
    source = open("frontend/src/pages/platforms/xhs/discovery-page.tsx", encoding="utf-8").read()

    assert "function getNoteKindLabel" in source
    assert "视频" in source
    assert "图文" in source


def test_rewrite_page_preserves_mode_switch():
    source = open("frontend/src/pages/platforms/xhs/rewrite-page.tsx", encoding="utf-8").read()

    assert "rewrite" in source
    assert "generate" in source
    assert "改写" in source
    assert "生成" in source
    assert "antd" in source


def test_publish_page_uses_antd_components():
    source = open("frontend/src/pages/platforms/xhs/publish-page.tsx", encoding="utf-8").read()

    assert "antd" in source
    assert "发布" in source


def test_database_initialization_creates_user_table(tmp_path):
    from alembic import command
    from alembic.config import Config

    db_url = f"sqlite:///{tmp_path / 'init-test.db'}"
    cfg = Config(os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "backend", "alembic.ini")))
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")

    test_engine = create_engine(db_url, connect_args={"check_same_thread": False})
    table_names = inspect(test_engine).get_table_names()
    assert "users" in table_names
    assert "platform_accounts" in table_names
    assert "alembic_version" in table_names


def test_alembic_initial_migration_creates_all_product_tables(tmp_path):
    from alembic import command
    from alembic.config import Config

    db_url = f"sqlite:///{tmp_path / 'alembic-tables-test.db'}"
    cfg = Config(os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "backend", "alembic.ini")))
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")

    test_engine = create_engine(db_url, connect_args={"check_same_thread": False})
    table_names = set(inspect(test_engine).get_table_names())
    expected = {
        "users", "platform_accounts", "account_cookie_versions", "login_sessions",
        "notes", "note_assets", "note_comments", "tags", "note_tags",
        "model_configs", "ai_drafts", "ai_generated_assets",
        "publish_jobs", "publish_assets", "tasks",
        "monitoring_targets", "monitoring_snapshots",
        "keyword_groups", "api_logs",
    }
    assert expected.issubset(table_names)


def test_database_initialization_normalizes_legacy_gpt_54_model_name(tmp_path):
    from backend.app.core.database import _normalize_model_config_names

    engine = create_engine(f"sqlite:///{tmp_path / 'model-name-migration-test.db'}", connect_args={"check_same_thread": False})
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE model_configs (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    name VARCHAR(128) NOT NULL,
                    model_type VARCHAR(32) NOT NULL,
                    provider VARCHAR(64) NOT NULL,
                    model_name VARCHAR(128) NOT NULL,
                    base_url TEXT NOT NULL,
                    encrypted_api_key TEXT NOT NULL,
                    is_default BOOLEAN NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                "INSERT INTO model_configs "
                "(id, user_id, name, model_type, provider, model_name, base_url, encrypted_api_key, is_default) "
                "VALUES (1, 1, 'Text model', 'text', 'openai-compatible', 'gpt5.4', 'https://api.example.test/v1', '', 1)"
            )
        )

    _normalize_model_config_names(engine)
    with engine.connect() as connection:
        row = connection.execute(text("SELECT model_name FROM model_configs WHERE id = 1")).mappings().one()
        assert row["model_name"] == "gpt-5.4"
        assert connection.execute(
            text("SELECT name FROM app_migrations WHERE name = 'normalize_legacy_gpt_54_model_name_v1'")
        ).first()


def test_database_initialization_normalizes_existing_sqlite_times_to_shanghai(tmp_path):
    from backend.app.core.database import _normalize_sqlite_datetime_storage

    engine = create_engine(f"sqlite:///{tmp_path / 'time-migration-test.db'}", connect_args={"check_same_thread": False})
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE platform_accounts (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    platform VARCHAR(32) NOT NULL,
                    sub_type VARCHAR(32),
                    external_user_id VARCHAR(128) NOT NULL,
                    nickname VARCHAR(128) NOT NULL,
                    avatar_url TEXT NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    status_message TEXT NOT NULL DEFAULT '',
                    profile_json TEXT NOT NULL DEFAULT '{}',
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME
                )
                """
            )
        )
        connection.execute(
            text(
                "INSERT INTO platform_accounts "
                "(id, user_id, platform, sub_type, external_user_id, nickname, avatar_url, status, created_at, updated_at) "
                "VALUES (1, 1, 'xhs', 'pc', 'pc-1', 'cat', '', 'active', '2026-04-30 07:50:43', '2026-04-30 07:50:43')"
            )
        )

    _normalize_sqlite_datetime_storage(engine)
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT created_at, updated_at FROM platform_accounts WHERE id = 1")
        ).mappings().one()
        assert str(row["created_at"]).startswith("2026-04-30 15:50:43")
        assert str(row["updated_at"]).startswith("2026-04-30 15:50:43")
        assert connection.execute(
            text("SELECT name FROM app_migrations WHERE name = 'sqlite_datetime_asia_shanghai_v1'")
        ).first()


def _parse_sse_response(response):
    import json as _json
    events = []
    done = {}
    for line in response.text.split("\n"):
        if line.startswith("data: "):
            event = _json.loads(line[6:])
            if event.get("type") == "item":
                events.append(event["item"])
            elif event.get("type") == "done":
                done = event
    return {"items": events, **done}


def _override_database(tmp_path):
    from backend.app.core.database import Base, get_db

    engine = create_engine(f"sqlite:///{tmp_path / 'auth-test.db'}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return get_db


def test_auth_register_login_me_and_refresh_use_real_tokens(tmp_path):
    get_db = _override_database(tmp_path)
    try:
        register_response = client.post(
            "/api/auth/register",
            json={"username": "operator", "password": "secret123"},
        )
        assert register_response.status_code == 200
        registered = register_response.json()
        assert registered["token_type"] == "bearer"
        assert registered["access_token"]
        assert registered["refresh_token"]
        assert registered["user"]["username"] == "operator"

        me_response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {registered['access_token']}"},
        )
        assert me_response.status_code == 200
        assert me_response.json()["username"] == "operator"

        login_response = client.post(
            "/api/auth/login",
            json={"username": "operator", "password": "secret123"},
        )
        assert login_response.status_code == 200
        logged_in = login_response.json()
        assert logged_in["access_token"]
        assert logged_in["refresh_token"]

        refresh_response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": logged_in["refresh_token"]},
        )
        assert refresh_response.status_code == 200
        refreshed = refresh_response.json()
        assert refreshed["token_type"] == "bearer"
        assert refreshed["access_token"]
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_auth_rejects_duplicate_user_and_bad_credentials(tmp_path):
    get_db = _override_database(tmp_path)
    try:
        response = client.post(
            "/api/auth/register",
            json={"username": "operator", "password": "secret123"},
        )
        assert response.status_code == 200

        duplicate_response = client.post(
            "/api/auth/register",
            json={"username": "operator", "password": "different123"},
        )
        assert duplicate_response.status_code == 400

        bad_login_response = client.post(
            "/api/auth/login",
            json={"username": "operator", "password": "wrong-password"},
        )
        assert bad_login_response.status_code == 401

        missing_auth_response = client.get("/api/auth/me")
        assert missing_auth_response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


class FakePcLoginAdapter:
    def create_qrcode(self):
        return {
            "cookies": {"a1": "temp-a1"},
            "qr_id": "qr-123",
            "code": "code-123",
            "qr_url": "https://example.test/qr",
        }

    def check_qrcode_status(self, qr_id, code, cookies):
        assert qr_id == "qr-123"
        assert code == "code-123"
        assert cookies == {"a1": "temp-a1"}
        return {"status": "confirmed", "cookies": {"a1": "final-a1", "web_session": "session-123"}}

    def get_user_info(self, cookies):
        assert cookies["web_session"] == "session-123"
        return {
            "external_user_id": "xhs-user-1",
            "nickname": "cat",
            "avatar_url": "https://example.test/avatar.webp",
        }


class FakeCreatorLoginAdapter:
    def create_qrcode(self):
        return {
            "cookies": {"a1": "creator-temp-a1"},
            "qr_id": "creator-qr-123",
            "qr_url": "https://example.test/creator-qr",
        }

    def check_qrcode_status(self, qr_id, cookies):
        assert qr_id == "creator-qr-123"
        assert cookies == {"a1": "creator-temp-a1"}
        return {"status": "confirmed", "cookies": {"a1": "creator-final-a1", "customer_session": "session-456"}}

    def get_user_info(self, cookies):
        assert cookies["customer_session"] == "session-456"
        return {
            "external_user_id": "creator-user-1",
            "nickname": "creator-cat",
            "avatar_url": "https://example.test/creator-avatar.webp",
        }


class FailingQrLoginAdapter:
    def create_qrcode(self):
        raise RuntimeError("proxy refused while creating qrcode")


class FakePhoneLoginAdapter:
    def create_phone_session(self, phone):
        assert phone == "13800138000"
        return {"cookies": {"a1": "phone-temp-a1"}, "message": "sent"}

    def confirm_phone_login(self, phone, code, cookies):
        assert phone == "13800138000"
        assert code == "123456"
        assert cookies == {"a1": "phone-temp-a1"}
        return {"status": "confirmed", "cookies": {"a1": "phone-final-a1", "web_session": "phone-session"}}

    def get_user_info(self, cookies):
        assert cookies["web_session"] == "phone-session"
        return {
            "external_user_id": "phone-user-1",
            "nickname": "phone-cat",
            "avatar_url": "https://example.test/phone-avatar.webp",
        }


def _register_and_get_access_token(username: str = "operator") -> str:
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": "secret123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_xhs_pc_qrcode_login_session_persists_and_confirms_account(tmp_path):
    from backend.app.api.login_sessions import get_pc_login_adapter
    from backend.app.core.database import get_db
    from backend.app.core.security import decrypt_text
    from backend.app.models import AccountCookieVersion, LoginSession, PlatformAccount

    db_dependency = _override_database(tmp_path)
    app.dependency_overrides[get_pc_login_adapter] = lambda: FakePcLoginAdapter()
    try:
        access_token = _register_and_get_access_token()

        create_response = client.post(
            "/api/xhs/login-sessions/pc/qrcode",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert create_response.status_code == 200
        created = create_response.json()
        assert created["status"] == "pending"
        assert created["qr_url"] == "https://example.test/qr"
        assert created["qr_image_data_url"].startswith("data:image/png;base64,")
        assert isinstance(created["session_id"], int)

        db = next(app.dependency_overrides[get_db]())
        try:
            stored_session = db.get(LoginSession, created["session_id"])
            assert stored_session.platform == "xhs"
            assert stored_session.sub_type == "pc"
            assert stored_session.qr_id == "qr-123"
            assert stored_session.code == "code-123"
            assert decrypt_text(stored_session.encrypted_temp_cookies) == '{"a1":"temp-a1"}'
        finally:
            db.close()

        poll_response = client.get(
            f"/api/xhs/login-sessions/{created['session_id']}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert poll_response.status_code == 200
        polled = poll_response.json()
        assert polled["status"] == "confirmed"
        assert polled["account"]["nickname"] == "cat"

        accounts_response = client.get(
            "/api/accounts?platform=xhs",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert accounts_response.status_code == 200
        accounts_payload = accounts_response.json()
        assert accounts_payload["total"] == 1
        assert accounts_payload["items"][0]["nickname"] == "cat"
        assert accounts_payload["items"][0]["sub_type"] == "pc"

        db = next(app.dependency_overrides[get_db]())
        try:
            account = db.query(PlatformAccount).one()
            assert account.platform == "xhs"
            assert account.sub_type == "pc"
            assert account.external_user_id == "xhs-user-1"
            cookie_version = db.query(AccountCookieVersion).one()
            assert cookie_version.platform_account_id == account.id
            assert decrypt_text(cookie_version.encrypted_cookies) == '{"a1":"final-a1","web_session":"session-123"}'
        finally:
            db.close()
    finally:
        app.dependency_overrides.pop(db_dependency, None)
        app.dependency_overrides.pop(get_pc_login_adapter, None)


def test_xhs_pc_qrcode_login_updates_existing_account_for_same_external_user(tmp_path):
    from backend.app.api.accounts import get_pc_account_adapter
    from backend.app.api.login_sessions import get_pc_login_adapter
    from backend.app.core.database import get_db
    from backend.app.core.security import decrypt_text
    from backend.app.models import AccountCookieVersion, PlatformAccount

    db_dependency = _override_database(tmp_path)
    app.dependency_overrides[get_pc_login_adapter] = lambda: FakePcLoginAdapter()
    app.dependency_overrides[get_pc_account_adapter] = lambda: FakePcLoginAdapter()
    try:
        access_token = _register_and_get_access_token("qr-upsert-operator")

        first_create = client.post(
            "/api/xhs/login-sessions/pc/qrcode",
            headers={"Authorization": f"Bearer {access_token}"},
        ).json()
        first_poll = client.get(
            f"/api/xhs/login-sessions/{first_create['session_id']}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert first_poll.status_code == 200
        assert first_poll.json()["account"]["action"] == "created"

        second_create = client.post(
            "/api/xhs/login-sessions/pc/qrcode",
            headers={"Authorization": f"Bearer {access_token}"},
        ).json()
        second_poll = client.get(
            f"/api/xhs/login-sessions/{second_create['session_id']}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert second_poll.status_code == 200
        assert second_poll.json()["account"]["action"] == "updated"

        accounts_response = client.get(
            "/api/accounts?platform=xhs",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        accounts_payload = accounts_response.json()
        assert accounts_payload["total"] == 1
        assert accounts_payload["items"][0]["updated_at"]
        assert accounts_payload["items"][0]["profile"] == {}

        check_response = client.post(
            f"/api/accounts/{accounts_payload['items'][0]['id']}/check",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert check_response.status_code == 200
        assert check_response.json()["status"] == "active", check_response.json().get("status_message")

        db = next(app.dependency_overrides[get_db]())
        try:
            accounts = db.query(PlatformAccount).all()
            assert len(accounts) == 1
            cookie_versions = db.query(AccountCookieVersion).order_by(AccountCookieVersion.id).all()
            assert len(cookie_versions) == 2
            assert cookie_versions[-1].platform_account_id == accounts[0].id
            assert decrypt_text(cookie_versions[-1].encrypted_cookies) == '{"a1":"final-a1","web_session":"session-123"}'
        finally:
            db.close()
    finally:
        app.dependency_overrides.pop(db_dependency, None)
        app.dependency_overrides.pop(get_pc_login_adapter, None)
        app.dependency_overrides.pop(get_pc_account_adapter, None)


def test_xhs_creator_qrcode_login_session_persists_and_confirms_account(tmp_path):
    from backend.app.api.login_sessions import get_creator_login_adapter
    from backend.app.core.database import get_db
    from backend.app.core.security import decrypt_text
    from backend.app.models import LoginSession, PlatformAccount

    db_dependency = _override_database(tmp_path)
    app.dependency_overrides[get_creator_login_adapter] = lambda: FakeCreatorLoginAdapter()
    try:
        access_token = _register_and_get_access_token("creator-operator")

        create_response = client.post(
            "/api/xhs/login-sessions/creator/qrcode",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert create_response.status_code == 200
        created = create_response.json()
        assert created["status"] == "pending"
        assert created["qr_url"] == "https://example.test/creator-qr"
        assert created["qr_image_data_url"].startswith("data:image/png;base64,")

        db = next(app.dependency_overrides[get_db]())
        try:
            stored_session = db.get(LoginSession, created["session_id"])
            assert stored_session.platform == "xhs"
            assert stored_session.sub_type == "creator"
            assert stored_session.qr_id == "creator-qr-123"
            assert stored_session.code is None
            assert decrypt_text(stored_session.encrypted_temp_cookies) == '{"a1":"creator-temp-a1"}'
        finally:
            db.close()

        poll_response = client.get(
            f"/api/xhs/login-sessions/{created['session_id']}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert poll_response.status_code == 200
        polled = poll_response.json()
        assert polled["status"] == "confirmed"
        assert polled["account"]["nickname"] == "creator-cat"

        accounts_response = client.get(
            "/api/accounts?platform=xhs",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        accounts_payload = accounts_response.json()
        assert accounts_payload["total"] == 1
        assert accounts_payload["items"][0]["sub_type"] == "creator"
        assert accounts_payload["items"][0]["nickname"] == "creator-cat"

        db = next(app.dependency_overrides[get_db]())
        try:
            account = db.query(PlatformAccount).one()
            assert account.sub_type == "creator"
            assert account.external_user_id == "creator-user-1"
        finally:
            db.close()
    finally:
        app.dependency_overrides.pop(db_dependency, None)
        app.dependency_overrides.pop(get_creator_login_adapter, None)


def test_xhs_pc_qrcode_reports_adapter_failure_as_bad_gateway(tmp_path):
    from backend.app.api.login_sessions import get_pc_login_adapter

    db_dependency = _override_database(tmp_path)
    app.dependency_overrides[get_pc_login_adapter] = lambda: FailingQrLoginAdapter()
    try:
        access_token = _register_and_get_access_token("qr-failure-operator")
        response = client.post(
            "/api/xhs/login-sessions/pc/qrcode",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 502
        assert "proxy refused" in response.json()["detail"]
    finally:
        app.dependency_overrides.pop(db_dependency, None)
        app.dependency_overrides.pop(get_pc_login_adapter, None)


def test_xhs_pc_phone_login_session_sends_code_and_confirms_account(tmp_path):
    from backend.app.api.login_sessions import get_pc_login_adapter
    from backend.app.core.database import get_db
    from backend.app.core.security import decrypt_text
    from backend.app.models import LoginSession, PlatformAccount

    db_dependency = _override_database(tmp_path)
    app.dependency_overrides[get_pc_login_adapter] = lambda: FakePhoneLoginAdapter()
    try:
        access_token = _register_and_get_access_token("phone-operator")

        send_response = client.post(
            "/api/xhs/login-sessions/pc/phone/send-code",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"phone": "13800138000"},
        )
        assert send_response.status_code == 200
        sent = send_response.json()
        assert sent["status"] == "pending"
        assert sent["message"] == "sent"

        db = next(app.dependency_overrides[get_db]())
        try:
            stored_session = db.get(LoginSession, sent["session_id"])
            assert stored_session.sub_type == "pc"
            assert stored_session.login_method == "phone"
            assert stored_session.phone_mask == "138****8000"
            assert decrypt_text(stored_session.encrypted_temp_cookies) == '{"a1":"phone-temp-a1"}'
        finally:
            db.close()

        confirm_response = client.post(
            "/api/xhs/login-sessions/pc/phone/confirm",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"session_id": sent["session_id"], "phone": "13800138000", "code": "123456"},
        )
        assert confirm_response.status_code == 200
        confirmed = confirm_response.json()
        assert confirmed["status"] == "confirmed"
        assert confirmed["account"]["nickname"] == "phone-cat"

        db = next(app.dependency_overrides[get_db]())
        try:
            account = db.query(PlatformAccount).one()
            assert account.sub_type == "pc"
            assert account.external_user_id == "phone-user-1"
        finally:
            db.close()
    finally:
        app.dependency_overrides.pop(db_dependency, None)
        app.dependency_overrides.pop(get_pc_login_adapter, None)


def test_xhs_creator_phone_login_session_sends_code_and_confirms_account(tmp_path):
    from backend.app.api.login_sessions import get_creator_login_adapter

    db_dependency = _override_database(tmp_path)
    app.dependency_overrides[get_creator_login_adapter] = lambda: FakePhoneLoginAdapter()
    try:
        access_token = _register_and_get_access_token("creator-phone-operator")

        send_response = client.post(
            "/api/xhs/login-sessions/creator/phone/send-code",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"phone": "13800138000"},
        )
        assert send_response.status_code == 200
        sent = send_response.json()
        assert sent["status"] == "pending"

        confirm_response = client.post(
            "/api/xhs/login-sessions/creator/phone/confirm",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"session_id": sent["session_id"], "phone": "13800138000", "code": "123456"},
        )
        assert confirm_response.status_code == 200
        confirmed = confirm_response.json()
        assert confirmed["status"] == "confirmed"
        assert confirmed["account"]["nickname"] == "phone-cat"

        accounts_response = client.get(
            "/api/accounts?platform=xhs",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        accounts_payload = accounts_response.json()
        assert accounts_payload["items"][0]["sub_type"] == "creator"
    finally:
        app.dependency_overrides.pop(db_dependency, None)
        app.dependency_overrides.pop(get_creator_login_adapter, None)


def test_account_delete_requires_owner_and_removes_account(tmp_path):
    from backend.app.core.database import get_db
    from backend.app.models import PlatformAccount

    db_dependency = _override_database(tmp_path)
    try:
        owner_token = _register_and_get_access_token("delete-account-owner")
        intruder_token = _register_and_get_access_token("delete-account-intruder")
        db = next(app.dependency_overrides[get_db]())
        try:
            account = PlatformAccount(
                user_id=1,
                platform="xhs",
                sub_type="pc",
                external_user_id="delete-user",
                nickname="Delete Me",
                status="active",
            )
            db.add(account)
            db.commit()
            db.refresh(account)
            account_id = account.id
        finally:
            db.close()

        intruder_response = client.delete(
            f"/api/accounts/{account_id}",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_response.status_code == 404

        owner_response = client.delete(
            f"/api/accounts/{account_id}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert owner_response.status_code == 200
        assert owner_response.json() == {"id": account_id, "status": "deleted"}

        accounts_response = client.get(
            "/api/accounts?platform=xhs",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert accounts_response.json()["total"] == 0
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_xhs_pc_qrcode_requires_platform_login(tmp_path):
    get_db = _override_database(tmp_path)
    try:
        response = client.post("/api/xhs/login-sessions/pc/qrcode")
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_accounts_list_requires_platform_login(tmp_path):
    get_db = _override_database(tmp_path)
    try:
        response = client.get("/api/accounts?platform=xhs")
        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)


class FakeCookieAccountAdapter:
    def __init__(self):
        self.calls = 0

    def get_user_info(self, cookies):
        self.calls += 1
        assert cookies["a1"] == "cookie-a1"
        return {
            "external_user_id": "cookie-user-1",
            "nickname": "cookie-cat",
            "avatar_url": "https://example.test/cookie-avatar.webp",
        }


class FakeSelfProfileAdapter:
    calls = []

    def get_self_profile(self, cookies_text):
        self.__class__.calls.append(cookies_text)
        return {
            "success": True,
            "msg": "ok",
            "data": {
                "basic_info": {
                    "nickname": "cookie-cat-live",
                    "images": "https://example.test/live-avatar.webp",
                    "red_id": "red-cookie-1",
                    "desc": "live profile",
                    "ip_location": "上海",
                },
                "interactions": [
                    {"type": "follows", "name": "关注", "count": "28", "i18n_count": "28"},
                    {"type": "fans", "name": "粉丝", "count": "90", "i18n_count": "90"},
                    {"type": "interaction", "name": "获赞与收藏", "count": "340", "i18n_count": "340"},
                ],
            },
            "code": 0,
        }


class FailingCookieAccountAdapter:
    def get_user_info(self, cookies):
        raise RuntimeError("expired")


def test_account_cookie_import_creates_account_and_health_check_updates_status(tmp_path):
    from backend.app.api.accounts import get_creator_account_adapter, get_pc_account_adapter
    from backend.app.core.database import get_db
    from backend.app.core.security import decrypt_text
    from backend.app.core.time import shanghai_now
    from backend.app.models import AccountCookieVersion, PlatformAccount

    db_dependency = _override_database(tmp_path)
    fake_adapter = FakeCookieAccountAdapter()
    app.dependency_overrides[get_pc_account_adapter] = lambda: fake_adapter
    app.dependency_overrides[get_creator_account_adapter] = lambda: fake_adapter
    try:
        access_token = _register_and_get_access_token("cookie-operator")
        before_create = shanghai_now()

        import_response = client.post(
            "/api/accounts/import-cookie",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"platform": "xhs", "sub_type": "pc", "cookie_string": "a1=cookie-a1; web_session=session"},
        )
        after_create = shanghai_now()
        assert import_response.status_code == 200
        imported = import_response.json()
        assert imported["nickname"] == "cookie-cat"
        assert imported["status"] == "active"

        db = next(app.dependency_overrides[get_db]())
        try:
            account = db.query(PlatformAccount).one()
            assert account.external_user_id == "cookie-user-1"
            assert before_create <= account.created_at <= after_create
            assert before_create <= account.updated_at <= after_create
            cookie_version = db.query(AccountCookieVersion).one()
            assert cookie_version.platform_account_id == account.id
            assert decrypt_text(cookie_version.encrypted_cookies) == "a1=cookie-a1; web_session=session"
        finally:
            db.close()

        check_response = client.post(
            f"/api/accounts/{imported['id']}/check",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert check_response.status_code == 200
        checked = check_response.json()
        assert checked["status"] == "active"
        assert checked["nickname"] == "cookie-cat"
        assert fake_adapter.calls >= 2
    finally:
        app.dependency_overrides.pop(db_dependency, None)
        app.dependency_overrides.pop(get_pc_account_adapter, None)
        app.dependency_overrides.pop(get_creator_account_adapter, None)


def test_account_check_refreshes_xhs_self_profile_metrics(tmp_path):
    from backend.app.api.accounts import (
        get_creator_account_adapter,
        get_pc_account_adapter,
        get_xhs_self_profile_adapter,
    )

    db_dependency = _override_database(tmp_path)
    fake_adapter = FakeCookieAccountAdapter()
    FakeSelfProfileAdapter.calls = []
    app.dependency_overrides[get_pc_account_adapter] = lambda: fake_adapter
    app.dependency_overrides[get_creator_account_adapter] = lambda: fake_adapter
    app.dependency_overrides[get_xhs_self_profile_adapter] = lambda: FakeSelfProfileAdapter()
    try:
        access_token = _register_and_get_access_token("profile-metrics-operator")
        import_response = client.post(
            "/api/accounts/import-cookie",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"platform": "xhs", "sub_type": "pc", "cookie_string": "a1=cookie-a1; web_session=session"},
        )
        account_id = import_response.json()["id"]

        check_response = client.post(
            f"/api/accounts/{account_id}/check",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert check_response.status_code == 200
        checked = check_response.json()
        assert checked["status"] == "active"
        assert checked["nickname"] == "cookie-cat-live"
        assert checked["avatar_url"] == "https://example.test/live-avatar.webp"
        assert checked["profile"]["followers"] == "90"
        assert checked["profile"]["following"] == "28"
        assert checked["profile"]["likes"] == "340"
        assert checked["profile"]["red_id"] == "red-cookie-1"
        assert FakeSelfProfileAdapter.calls == ["a1=cookie-a1; web_session=session", "a1=cookie-a1; web_session=session"]
    finally:
        app.dependency_overrides.pop(db_dependency, None)
        app.dependency_overrides.pop(get_pc_account_adapter, None)
        app.dependency_overrides.pop(get_creator_account_adapter, None)
        app.dependency_overrides.pop(get_xhs_self_profile_adapter, None)


def test_account_check_enforces_ownership_and_marks_expired_on_adapter_failure(tmp_path):
    from backend.app.api.accounts import get_pc_account_adapter

    db_dependency = _override_database(tmp_path)
    app.dependency_overrides[get_pc_account_adapter] = lambda: FakeCookieAccountAdapter()
    try:
        owner_token = _register_and_get_access_token("owner-operator")
        intruder_token = _register_and_get_access_token("intruder-operator")

        import_response = client.post(
            "/api/accounts/import-cookie",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform": "xhs", "sub_type": "pc", "cookie_string": "a1=cookie-a1; web_session=session"},
        )
        account_id = import_response.json()["id"]

        forbidden_response = client.post(
            f"/api/accounts/{account_id}/check",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert forbidden_response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_pc_account_adapter, None)

    app.dependency_overrides[get_pc_account_adapter] = lambda: FailingCookieAccountAdapter()
    try:
        expired_response = client.post(
            f"/api/accounts/{account_id}/check",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert expired_response.status_code == 200
        assert expired_response.json()["status"] == "expired"
    finally:
        app.dependency_overrides.pop(db_dependency, None)
        app.dependency_overrides.pop(get_pc_account_adapter, None)


class FakeXhsPcSearchAdapter:
    calls = []

    def __init__(self, cookies):
        self.cookies = cookies

    def search_note(self, keyword, page=1, **kwargs):
        self.__class__.calls.append({"cookies": self.cookies, "keyword": keyword, "page": page, **kwargs})
        return (
            True,
            "ok",
            {
                "success": True,
                "msg": "ok",
                "data": {
                    "has_more": True,
                    "items": [
                        {
                            "model_type": "note",
                            "xsec_token": "xsec-search-001",
                            "note_card": {
                                "note_id": "note-001",
                                "display_title": "低卡早餐搜索笔记",
                                "desc": "适合工作日的早餐搭配",
                                "type": "normal",
                                "user": {
                                    "user_id": "author-001",
                                    "nickname": "早餐研究员",
                                    "avatar": "https://example.test/avatar.webp",
                                },
                                "cover": {"url_default": "https://example.test/cover.webp"},
                                "interact_info": {
                                    "liked_count": "1234",
                                    "collected_count": "456",
                                    "comment_count": "78",
                                    "share_count": "9",
                                },
                            },
                        }
                    ],
                },
            },
        )


def _create_pc_account_with_cookie(tmp_path, username="search-owner"):
    from backend.app.core.database import get_db
    from backend.app.core.security import encrypt_text
    from backend.app.models import AccountCookieVersion, PlatformAccount

    db_dependency = _override_database(tmp_path)
    access_token = _register_and_get_access_token(username)
    db = next(app.dependency_overrides[get_db]())
    try:
        account = PlatformAccount(
            user_id=1,
            platform="xhs",
            sub_type="pc",
            external_user_id="search-user",
            nickname="搜索账号",
            status="active",
        )
        db.add(account)
        db.flush()
        db.add(
            AccountCookieVersion(
                platform_account_id=account.id,
                encrypted_cookies=encrypt_text('{"a1":"json-a1","web_session":"json-session"}'),
            )
        )
        db.commit()
        account_id = account.id
    finally:
        db.close()
    return db_dependency, access_token, account_id


def _create_creator_account_with_cookie(tmp_path, username="creator-owner"):
    from backend.app.core.database import get_db
    from backend.app.core.security import encrypt_text
    from backend.app.models import AccountCookieVersion, PlatformAccount

    db_dependency = _override_database(tmp_path)
    access_token = _register_and_get_access_token(username)
    db = next(app.dependency_overrides[get_db]())
    try:
        account = PlatformAccount(
            user_id=1,
            platform="xhs",
            sub_type="creator",
            external_user_id="creator-user",
            nickname="Creator account",
            status="active",
        )
        db.add(account)
        db.flush()
        db.add(
            AccountCookieVersion(
                platform_account_id=account.id,
                encrypted_cookies=encrypt_text('{"web_session":"creator-session","a1":"creator-a1"}'),
            )
        )
        db.commit()
        account_id = account.id
    finally:
        db.close()
    return db_dependency, access_token, account_id


def test_xhs_pc_note_search_uses_owned_account_cookie_and_normalizes_results(tmp_path):
    from backend.app.api.platforms.xhs.pc import get_xhs_pc_api_adapter_factory

    db_dependency, access_token, account_id = _create_pc_account_with_cookie(tmp_path)
    FakeXhsPcSearchAdapter.calls = []
    app.dependency_overrides[get_xhs_pc_api_adapter_factory] = lambda: FakeXhsPcSearchAdapter
    try:
        response = client.post(
            "/api/xhs/pc/search/notes",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"account_id": account_id, "keyword": "低卡早餐", "page": 2},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 1
        assert payload["page"] == 2
        assert payload["has_more"] is True
        assert FakeXhsPcSearchAdapter.calls == [
            {
                "cookies": "a1=json-a1; web_session=json-session",
                "keyword": "低卡早餐",
                "page": 2,
                "sort_type_choice": 0,
                "note_type": 0,
                "note_time": 0,
                "note_range": 0,
                "pos_distance": 0,
                "geo": "",
            }
        ]
        note = payload["items"][0]
        assert note["note_id"] == "note-001"
        assert note["note_url"] == "https://www.xiaohongshu.com/explore/note-001?xsec_token=xsec-search-001&xsec_source=pc_feed"
        assert note["title"] == "低卡早餐搜索笔记"
        assert note["content"] == "适合工作日的早餐搭配"
        assert note["author_name"] == "早餐研究员"
        assert note["author_id"] == "author-001"
        assert note["cover_url"] == "https://example.test/cover.webp"
        assert note["likes"] == 1234
        assert note["collects"] == 456
        assert note["comments"] == 78
        assert note["shares"] == 9
        assert note["type"] == "normal"
        assert note["raw"]["model_type"] == "note"
    finally:
        app.dependency_overrides.pop(db_dependency, None)
        app.dependency_overrides.pop(get_xhs_pc_api_adapter_factory, None)


def test_xhs_pc_note_search_rejects_missing_auth_and_cross_user_account(tmp_path):
    from backend.app.api.platforms.xhs.pc import get_xhs_pc_api_adapter_factory

    db_dependency, owner_token, account_id = _create_pc_account_with_cookie(tmp_path, "search-owner-2")
    intruder_token = _register_and_get_access_token("search-intruder")
    app.dependency_overrides[get_xhs_pc_api_adapter_factory] = lambda: FakeXhsPcSearchAdapter
    try:
        missing_auth_response = client.post(
            "/api/xhs/pc/search/notes",
            json={"account_id": account_id, "keyword": "低卡早餐", "page": 1},
        )
        assert missing_auth_response.status_code == 401

        intruder_response = client.post(
            "/api/xhs/pc/search/notes",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"account_id": account_id, "keyword": "低卡早餐", "page": 1},
        )
        assert intruder_response.status_code == 404

        owner_response = client.post(
            "/api/xhs/pc/search/notes",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"account_id": account_id, "keyword": "低卡早餐", "page": 1},
        )
        assert owner_response.status_code == 200
    finally:
        app.dependency_overrides.pop(db_dependency, None)
        app.dependency_overrides.pop(get_xhs_pc_api_adapter_factory, None)


def test_xhs_pc_note_detail_uses_owned_account_cookie_and_normalizes_result(tmp_path):
    from backend.app.api.platforms.xhs.pc import get_xhs_pc_api_adapter_factory

    class FakeXhsPcDetailAdapter:
        calls = []

        def __init__(self, cookies):
            self.cookies = cookies

        def get_note_info(self, url):
            self.calls.append({"cookies": self.cookies, "url": url})
            return (
                True,
                "ok",
                {
                    "success": True,
                    "data": {
                        "items": [
                            {
                                "note_card": {
                                    "note_id": "detail-note-001",
                                    "title": "Detail title",
                                    "desc": "Detail body",
                                    "type": "video",
                                    "user": {
                                        "user_id": "author-detail",
                                        "nickname": "Detail author",
                                        "avatar": "https://example.test/author.webp",
                                    },
                                    "image_list": [
                                        {
                                            "url_default": "https://example.test/image-preview.webp",
                                            "info_list": [
                                                {"image_scene": "WB_DFT", "url": "https://example.test/image-low.webp"},
                                                {"image_scene": "WB_PRV", "url": "https://example.test/image-high.webp"},
                                            ],
                                        },
                                    ],
                                    "video": {
                                        "media": {
                                            "stream": {
                                                "h264": [
                                                    {
                                                        "master_url": "https://sns-video-hw.xhscdn.com/detail-video-master.mp4",
                                                        "url": "https://sns-video-hw.xhscdn.com/detail-video-fallback.mp4",
                                                    }
                                                ]
                                            }
                                        }
                                    },
                                    "interact_info": {
                                        "liked_count": "100",
                                        "collected_count": "20",
                                        "comment_count": "3",
                                        "share_count": "4",
                                    },
                                    "tag_list": [{"name": "topic-a"}, {"name": "topic-b"}],
                                }
                            }
                        ]
                    },
                },
            )

    db_dependency, access_token, account_id = _create_pc_account_with_cookie(tmp_path, "detail-owner")
    FakeXhsPcDetailAdapter.calls = []
    app.dependency_overrides[get_xhs_pc_api_adapter_factory] = lambda: FakeXhsPcDetailAdapter
    try:
        response = client.post(
            "/api/xhs/pc/notes/detail",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "account_id": account_id,
                "url": "https://www.xiaohongshu.com/explore/detail-note-001?xsec_token=detail-token&xsec_source=pc_feed",
            },
        )

        assert response.status_code == 200
        detail = response.json()
        assert detail["note_id"] == "detail-note-001"
        assert detail["note_url"] == "https://www.xiaohongshu.com/explore/detail-note-001?xsec_token=detail-token&xsec_source=pc_feed"
        assert detail["title"] == "Detail title"
        assert detail["content"] == "Detail body"
        assert detail["author_id"] == "author-detail"
        assert detail["author_name"] == "Detail author"
        assert detail["cover_url"] == "https://example.test/image-high.webp"
        assert detail["image_urls"] == ["https://example.test/image-high.webp"]
        assert detail["video_url"] == "https://sns-video-hw.xhscdn.com/detail-video-master.mp4"
        assert detail["video_addr"] == "https://sns-video-hw.xhscdn.com/detail-video-master.mp4"
        assert detail["tags"] == ["topic-a", "topic-b"]
        assert detail["likes"] == 100
        assert FakeXhsPcDetailAdapter.calls == [
            {
                "cookies": "a1=json-a1; web_session=json-session",
                "url": "https://www.xiaohongshu.com/explore/detail-note-001?xsec_token=detail-token&xsec_source=pc_feed",
            }
        ]
    finally:
        app.dependency_overrides.pop(db_dependency, None)
        app.dependency_overrides.pop(get_xhs_pc_api_adapter_factory, None)


def test_xhs_pc_note_detail_rejects_missing_auth_and_cross_user_account(tmp_path):
    from backend.app.api.platforms.xhs.pc import get_xhs_pc_api_adapter_factory

    class FakeXhsPcDetailAdapter:
        def __init__(self, cookies):
            raise AssertionError("cross-user detail must not instantiate adapter")

    db_dependency, _, account_id = _create_pc_account_with_cookie(tmp_path, "detail-cross-owner")
    intruder_token = _register_and_get_access_token("detail-cross-intruder")
    app.dependency_overrides[get_xhs_pc_api_adapter_factory] = lambda: FakeXhsPcDetailAdapter
    try:
        anonymous_response = client.post(
            "/api/xhs/pc/notes/detail",
            json={"account_id": account_id, "url": "https://www.xiaohongshu.com/explore/detail-note-001"},
        )
        assert anonymous_response.status_code == 401

        intruder_response = client.post(
            "/api/xhs/pc/notes/detail",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"account_id": account_id, "url": "https://www.xiaohongshu.com/explore/detail-note-001"},
        )
        assert intruder_response.status_code == 404
    finally:
        app.dependency_overrides.pop(db_dependency, None)
        app.dependency_overrides.pop(get_xhs_pc_api_adapter_factory, None)


def test_xhs_pc_note_comments_uses_owned_account_cookie_and_normalizes_result(tmp_path):
    from backend.app.api.platforms.xhs.pc import get_xhs_pc_api_adapter_factory

    class FakeXhsPcCommentAdapter:
        calls = []

        def __init__(self, cookies):
            self.cookies = cookies

        def get_note_comments(self, note_url):
            self.calls.append({"cookies": self.cookies, "note_url": note_url})
            return (
                True,
                "ok",
                {
                    "data": {
                        "comments": [
                            {
                                "id": "comment-001",
                                "content": "Top level comment",
                                "like_count": "12",
                                "create_time": "2026-04-29 12:00:00",
                                "user_info": {"user_id": "user-001", "nickname": "Comment author"},
                                "sub_comments": [
                                    {
                                        "id": "comment-001-1",
                                        "content": "Reply content",
                                        "like_count": 3,
                                        "create_time": "2026-04-29 12:01:00",
                                        "user_info": {"user_id": "user-002", "nickname": "Reply author"},
                                    }
                                ],
                            }
                        ]
                    }
                },
            )

    db_dependency, access_token, account_id = _create_pc_account_with_cookie(tmp_path, "comments-owner")
    FakeXhsPcCommentAdapter.calls = []
    app.dependency_overrides[get_xhs_pc_api_adapter_factory] = lambda: FakeXhsPcCommentAdapter
    try:
        response = client.post(
            "/api/xhs/pc/notes/comments",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"account_id": account_id, "note_url": "https://www.xiaohongshu.com/explore/comment-note-001"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["total"] == 2
        assert payload["items"] == [
            {
                "comment_id": "comment-001",
                "user_name": "Comment author",
                "user_id": "user-001",
                "content": "Top level comment",
                "like_count": 12,
                "parent_comment_id": None,
                "created_at_remote": "2026-04-29 12:00:00",
                "raw_json": {
                    "id": "comment-001",
                    "content": "Top level comment",
                    "like_count": "12",
                    "create_time": "2026-04-29 12:00:00",
                    "user_info": {"user_id": "user-001", "nickname": "Comment author"},
                    "sub_comments": [
                        {
                            "id": "comment-001-1",
                            "content": "Reply content",
                            "like_count": 3,
                            "create_time": "2026-04-29 12:01:00",
                            "user_info": {"user_id": "user-002", "nickname": "Reply author"},
                        }
                    ],
                },
            },
            {
                "comment_id": "comment-001-1",
                "user_name": "Reply author",
                "user_id": "user-002",
                "content": "Reply content",
                "like_count": 3,
                "parent_comment_id": "comment-001",
                "created_at_remote": "2026-04-29 12:01:00",
                "raw_json": {
                    "id": "comment-001-1",
                    "content": "Reply content",
                    "like_count": 3,
                    "create_time": "2026-04-29 12:01:00",
                    "user_info": {"user_id": "user-002", "nickname": "Reply author"},
                },
            },
        ]
        assert FakeXhsPcCommentAdapter.calls == [
            {
                "cookies": "a1=json-a1; web_session=json-session",
                "note_url": "https://www.xiaohongshu.com/explore/comment-note-001",
            }
        ]
    finally:
        app.dependency_overrides.pop(db_dependency, None)
        app.dependency_overrides.pop(get_xhs_pc_api_adapter_factory, None)


def test_xhs_pc_note_comments_rejects_missing_auth_and_cross_user_account(tmp_path):
    from backend.app.api.platforms.xhs.pc import get_xhs_pc_api_adapter_factory

    class FakeXhsPcCommentAdapter:
        def __init__(self, cookies):
            raise AssertionError("cross-user comments must not instantiate adapter")

    db_dependency, _, account_id = _create_pc_account_with_cookie(tmp_path, "comments-cross-owner")
    intruder_token = _register_and_get_access_token("comments-cross-intruder")
    app.dependency_overrides[get_xhs_pc_api_adapter_factory] = lambda: FakeXhsPcCommentAdapter
    try:
        anonymous_response = client.post(
            "/api/xhs/pc/notes/comments",
            json={"account_id": account_id, "note_url": "https://www.xiaohongshu.com/explore/comment-note-001"},
        )
        assert anonymous_response.status_code == 401

        intruder_response = client.post(
            "/api/xhs/pc/notes/comments",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"account_id": account_id, "note_url": "https://www.xiaohongshu.com/explore/comment-note-001"},
        )
        assert intruder_response.status_code == 404
    finally:
        app.dependency_overrides.pop(db_dependency, None)
        app.dependency_overrides.pop(get_xhs_pc_api_adapter_factory, None)


def test_notes_batch_save_requires_authentication(tmp_path):
    db_dependency = _override_database(tmp_path)
    try:
        response = client.post(
            "/api/notes/batch-save",
            json={"account_id": 1, "notes": [{"note_id": "note-001", "title": "标题"}]},
        )

        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_notes_batch_save_persists_owned_search_results_and_updates_duplicates(tmp_path):
    from backend.app.core.database import get_db
    from backend.app.models import Note

    db_dependency, access_token, account_id = _create_pc_account_with_cookie(tmp_path, "save-owner")
    try:
        first_response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "account_id": account_id,
                "notes": [
                    {
                        "note_id": "note-save-001",
                        "title": "第一版标题",
                        "content": "第一版正文",
                        "author_name": "作者 A",
                        "raw": {"source": "search", "version": 1},
                    }
                ],
            },
        )
        assert first_response.status_code == 200
        first_payload = first_response.json()
        assert first_payload["saved_count"] == 1
        assert first_payload["items"][0]["note_id"] == "note-save-001"
        assert first_payload["items"][0]["title"] == "第一版标题"

        second_response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "account_id": account_id,
                "notes": [
                    {
                        "note_id": "note-save-001",
                        "title": "第二版标题",
                        "content": "第二版正文",
                        "author_name": "作者 B",
                        "raw": {"source": "search", "version": 2},
                    }
                ],
            },
        )
        assert second_response.status_code == 200
        assert second_response.json()["saved_count"] == 1

        db = next(app.dependency_overrides[get_db]())
        try:
            notes = db.query(Note).all()
            assert len(notes) == 1
            assert notes[0].platform == "xhs"
            assert notes[0].platform_account_id == account_id
            assert notes[0].note_id == "note-save-001"
            assert notes[0].title == "第二版标题"
            assert notes[0].content == "第二版正文"
            assert notes[0].author_name == "作者 B"
            assert notes[0].raw_json == {"source": "search", "version": 2}
        finally:
            db.close()
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_notes_batch_save_persists_detail_assets_and_lists_owned_assets(tmp_path):
    from backend.app.core.database import get_db
    from backend.app.models import NoteAsset

    db_dependency, access_token, account_id = _create_pc_account_with_cookie(tmp_path, "save-assets-owner")
    try:
        save_response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "account_id": account_id,
                "notes": [
                    {
                        "note_id": "note-assets-001",
                        "title": "Asset detail title",
                        "content": "Asset detail body",
                        "author_name": "Asset author",
                        "image_urls": [
                            "https://example.test/detail-1.webp",
                            "https://example.test/detail-2.webp",
                        ],
                        "video_addr": "https://example.test/detail-video.mp4",
                        "cover_url": "https://example.test/detail-cover.webp",
                        "raw": {"source": "detail"},
                    }
                ],
            },
        )
        assert save_response.status_code == 200
        saved_payload = save_response.json()["items"][0]
        note_id = saved_payload["id"]
        assert saved_payload["cover_url"] == "https://example.test/detail-1.webp"
        assert saved_payload["asset_urls"] == [
            "https://example.test/detail-1.webp",
            "https://example.test/detail-2.webp",
            "https://example.test/detail-video.mp4",
        ]

        list_response = client.get(
            f"/api/notes/{note_id}/assets",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert list_response.status_code == 200
        payload = list_response.json()
        assert payload["total"] == 3
        assert [(item["asset_type"], item["url"]) for item in payload["items"]] == [
            ("image", "https://example.test/detail-1.webp"),
            ("image", "https://example.test/detail-2.webp"),
            ("video", "https://example.test/detail-video.mp4"),
        ]

        note_detail_response = client.get(
            f"/api/notes/{note_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert note_detail_response.status_code == 200
        assert note_detail_response.json()["asset_urls"] == [
            "https://example.test/detail-1.webp",
            "https://example.test/detail-2.webp",
            "https://example.test/detail-video.mp4",
        ]

        update_response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "account_id": account_id,
                "notes": [
                    {
                        "note_id": "note-assets-001",
                        "title": "Asset detail title updated",
                        "image_urls": ["https://example.test/detail-2.webp"],
                    }
                ],
            },
        )
        assert update_response.status_code == 200

        db = next(app.dependency_overrides[get_db]())
        try:
            assets = db.query(NoteAsset).filter(NoteAsset.note_id == note_id).all()
            assert [(asset.asset_type, asset.url) for asset in assets] == [("image", "https://example.test/detail-2.webp")]
        finally:
            db.close()
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_notes_assets_reject_cross_user_note(tmp_path):
    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "assets-owner")
    intruder_token = _register_and_get_access_token("assets-intruder")
    try:
        save_response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "account_id": owner_account_id,
                "notes": [
                    {
                        "note_id": "note-assets-cross-001",
                        "title": "Owner note",
                        "image_urls": ["https://example.test/owner.webp"],
                    }
                ],
            },
        )
        note_id = save_response.json()["items"][0]["id"]

        response = client.get(
            f"/api/notes/{note_id}/assets",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )

        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_notes_batch_save_fetches_and_persists_comments(tmp_path):
    from backend.app.api.platforms.xhs.pc import get_xhs_pc_api_adapter_factory
    from backend.app.core.database import get_db
    from backend.app.models import NoteComment

    class FakeXhsPcCommentPersistAdapter:
        calls = []

        def __init__(self, cookies):
            self.cookies = cookies

        def get_note_comments(self, note_url):
            self.calls.append({"cookies": self.cookies, "note_url": note_url})
            return (
                True,
                "ok",
                {
                    "data": {
                        "comments": [
                            {
                                "id": "persist-comment-001",
                                "content": "Persisted top comment",
                                "like_count": "8",
                                "create_time": "2026-04-29 13:00:00",
                                "user_info": {"user_id": "persist-user-001", "nickname": "Persist author"},
                            }
                        ]
                    }
                },
            )

    db_dependency, access_token, account_id = _create_pc_account_with_cookie(tmp_path, "comment-persist-owner")
    FakeXhsPcCommentPersistAdapter.calls = []
    app.dependency_overrides[get_xhs_pc_api_adapter_factory] = lambda: FakeXhsPcCommentPersistAdapter
    try:
        save_response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "account_id": account_id,
                "fetch_comments": True,
                "notes": [
                    {
                        "note_id": "note-comments-001",
                        "note_url": "https://www.xiaohongshu.com/explore/note-comments-001",
                        "title": "Comment note",
                    }
                ],
            },
        )
        assert save_response.status_code == 200
        note_id = save_response.json()["items"][0]["id"]
        assert FakeXhsPcCommentPersistAdapter.calls == [
            {
                "cookies": "a1=json-a1; web_session=json-session",
                "note_url": "https://www.xiaohongshu.com/explore/note-comments-001",
            }
        ]

        list_response = client.get(
            f"/api/notes/{note_id}/comments",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert list_response.status_code == 200
        payload = list_response.json()
        assert payload["total"] == 1
        assert payload["items"][0]["comment_id"] == "persist-comment-001"
        assert payload["items"][0]["user_name"] == "Persist author"
        assert payload["items"][0]["user_id"] == "persist-user-001"
        assert payload["items"][0]["content"] == "Persisted top comment"
        assert payload["items"][0]["like_count"] == 8
        assert payload["items"][0]["parent_comment_id"] is None
        assert payload["items"][0]["created_at_remote"] == "2026-04-29 13:00:00"

        db = next(app.dependency_overrides[get_db]())
        try:
            comments = db.query(NoteComment).filter(NoteComment.note_id == note_id).all()
            assert len(comments) == 1
            assert comments[0].raw_json["id"] == "persist-comment-001"
        finally:
            db.close()
    finally:
        app.dependency_overrides.pop(db_dependency, None)
        app.dependency_overrides.pop(get_xhs_pc_api_adapter_factory, None)


def test_notes_batch_save_replaces_stale_comments_on_refetch(tmp_path):
    from backend.app.api.platforms.xhs.pc import get_xhs_pc_api_adapter_factory

    class FakeXhsPcCommentReplaceAdapter:
        calls = []

        def __init__(self, cookies):
            self.cookies = cookies

        def get_note_comments(self, note_url):
            self.calls.append(note_url)
            comment_id = "stale-comment" if len(self.calls) == 1 else "fresh-comment"
            return (
                True,
                "ok",
                {"data": {"comments": [{"id": comment_id, "content": comment_id, "user_info": {"nickname": "User"}}]}},
            )

    db_dependency, access_token, account_id = _create_pc_account_with_cookie(tmp_path, "comment-replace-owner")
    FakeXhsPcCommentReplaceAdapter.calls = []
    app.dependency_overrides[get_xhs_pc_api_adapter_factory] = lambda: FakeXhsPcCommentReplaceAdapter
    try:
        for _ in range(2):
            save_response = client.post(
                "/api/notes/batch-save",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "account_id": account_id,
                    "fetch_comments": True,
                    "notes": [
                        {
                            "note_id": "note-comments-replace-001",
                            "note_url": "https://www.xiaohongshu.com/explore/note-comments-replace-001",
                            "title": "Replace comments",
                        }
                    ],
                },
            )
            assert save_response.status_code == 200
        note_id = save_response.json()["items"][0]["id"]

        list_response = client.get(
            f"/api/notes/{note_id}/comments",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert list_response.status_code == 200
        assert list_response.json()["total"] == 1
        assert list_response.json()["items"][0]["comment_id"] == "fresh-comment"
    finally:
        app.dependency_overrides.pop(db_dependency, None)
        app.dependency_overrides.pop(get_xhs_pc_api_adapter_factory, None)


def test_notes_comments_list_requires_auth_and_enforces_ownership(tmp_path):
    from backend.app.api.platforms.xhs.pc import get_xhs_pc_api_adapter_factory

    class FakeXhsPcCommentListAdapter:
        def __init__(self, cookies):
            self.cookies = cookies

        def get_note_comments(self, note_url):
            return (
                True,
                "ok",
                {"data": {"comments": [{"id": "owned-comment", "content": "Owned", "user_info": {"nickname": "User"}}]}},
            )

    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "comments-list-owner")
    intruder_token = _register_and_get_access_token("comments-list-intruder")
    app.dependency_overrides[get_xhs_pc_api_adapter_factory] = lambda: FakeXhsPcCommentListAdapter
    try:
        save_response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "account_id": owner_account_id,
                "fetch_comments": True,
                "notes": [
                    {
                        "note_id": "note-comments-owned-001",
                        "note_url": "https://www.xiaohongshu.com/explore/note-comments-owned-001",
                        "title": "Owned comment note",
                    }
                ],
            },
        )
        note_id = save_response.json()["items"][0]["id"]

        anonymous_response = client.get(f"/api/notes/{note_id}/comments")
        assert anonymous_response.status_code == 401

        intruder_response = client.get(
            f"/api/notes/{note_id}/comments",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_response.status_code == 404
    finally:
        app.dependency_overrides.pop(db_dependency, None)
        app.dependency_overrides.pop(get_xhs_pc_api_adapter_factory, None)


def test_tags_crud_are_user_scoped_and_validate_duplicates(tmp_path):
    db_dependency = _override_database(tmp_path)
    try:
        owner_token = _register_and_get_access_token("tags-crud-owner")
        intruder_token = _register_and_get_access_token("tags-crud-intruder")

        create_response = client.post(
            "/api/tags",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"name": "High value", "color": "#111111"},
        )
        assert create_response.status_code == 200
        created = create_response.json()
        assert created["name"] == "High value"
        assert created["color"] == "#111111"

        duplicate_response = client.post(
            "/api/tags",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"name": "High value", "color": "#ef4444"},
        )
        assert duplicate_response.status_code == 400

        owner_list_response = client.get(
            "/api/tags",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert owner_list_response.status_code == 200
        assert owner_list_response.json()["total"] == 1

        intruder_list_response = client.get(
            "/api/tags",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_list_response.status_code == 200
        assert intruder_list_response.json()["total"] == 0

        intruder_update_response = client.patch(
            f"/api/tags/{created['id']}",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"name": "Stolen"},
        )
        assert intruder_update_response.status_code == 404

        update_response = client.patch(
            f"/api/tags/{created['id']}",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"name": "Rewrite queue", "color": "#2563eb"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "Rewrite queue"
        assert update_response.json()["color"] == "#2563eb"

        intruder_delete_response = client.delete(
            f"/api/tags/{created['id']}",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_delete_response.status_code == 404

        delete_response = client.delete(
            f"/api/tags/{created['id']}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert delete_response.status_code == 200
        assert delete_response.json() == {"id": created["id"], "status": "deleted"}

        empty_list_response = client.get(
            "/api/tags",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert empty_list_response.json()["total"] == 0
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_notes_batch_tag_applies_and_removes_owned_tags(tmp_path):
    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "batch-tag-owner")
    try:
        first_tag = client.post(
            "/api/tags",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"name": "Rewrite", "color": "#111111"},
        ).json()
        second_tag = client.post(
            "/api/tags",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"name": "Benchmark", "color": "#2563eb"},
        ).json()
        save_response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "account_id": owner_account_id,
                "notes": [
                    {
                        "note_id": "note-tags-001",
                        "title": "Tagged note",
                        "content": "Tag me",
                    }
                ],
            },
        )
        note_id = save_response.json()["items"][0]["id"]

        replace_response = client.post(
            "/api/notes/batch-tag",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"note_ids": [note_id], "tag_ids": [first_tag["id"]], "mode": "replace"},
        )
        assert replace_response.status_code == 200
        assert replace_response.json()["updated_count"] == 1
        assert replace_response.json()["items"][0]["tags"] == [first_tag]

        add_response = client.post(
            "/api/notes/batch-tag",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"note_ids": [note_id], "tag_ids": [second_tag["id"]], "mode": "add"},
        )
        assert add_response.status_code == 200
        assert [tag["name"] for tag in add_response.json()["items"][0]["tags"]] == ["Rewrite", "Benchmark"]

        remove_response = client.post(
            "/api/notes/batch-tag",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"note_ids": [note_id], "tag_ids": [first_tag["id"]], "mode": "remove"},
        )
        assert remove_response.status_code == 200
        assert remove_response.json()["items"][0]["tags"] == [second_tag]

        detail_response = client.get(
            f"/api/notes/{note_id}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert detail_response.status_code == 200
        assert detail_response.json()["tags"] == [second_tag]

        list_response = client.get(
            "/api/notes?platform=xhs",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert list_response.status_code == 200
        assert list_response.json()["items"][0]["tags"] == [second_tag]
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_notes_batch_tag_rejects_cross_user_note_or_tag(tmp_path):
    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "batch-tag-cross-owner")
    intruder_token = _register_and_get_access_token("batch-tag-cross-intruder")
    try:
        owner_tag = client.post(
            "/api/tags",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"name": "Owner tag", "color": "#111111"},
        ).json()
        intruder_tag = client.post(
            "/api/tags",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"name": "Intruder tag", "color": "#ef4444"},
        ).json()
        save_response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "account_id": owner_account_id,
                "notes": [{"note_id": "note-tags-cross-001", "title": "Owner note"}],
            },
        )
        note_id = save_response.json()["items"][0]["id"]

        intruder_note_response = client.post(
            "/api/notes/batch-tag",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"note_ids": [note_id], "tag_ids": [intruder_tag["id"]], "mode": "replace"},
        )
        assert intruder_note_response.status_code == 404

        owner_cross_tag_response = client.post(
            "/api/notes/batch-tag",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"note_ids": [note_id], "tag_ids": [intruder_tag["id"]], "mode": "replace"},
        )
        assert owner_cross_tag_response.status_code == 404

        owner_valid_response = client.post(
            "/api/notes/batch-tag",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"note_ids": [note_id], "tag_ids": [owner_tag["id"]], "mode": "replace"},
        )
        assert owner_valid_response.status_code == 200
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_notes_batch_create_drafts_creates_owned_drafts_and_rejects_cross_user_notes(tmp_path):
    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "batch-drafts-owner")
    intruder_token = _register_and_get_access_token("batch-drafts-intruder")
    try:
        save_response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "account_id": owner_account_id,
                "notes": [
                    {"note_id": "batch-draft-001", "title": "First source", "content": "First body"},
                    {"note_id": "batch-draft-002", "title": "Second source", "content": "Second body"},
                ],
            },
        )
        assert save_response.status_code == 200
        note_ids = [item["id"] for item in save_response.json()["items"]]

        response = client.post(
            "/api/notes/batch-create-drafts",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"note_ids": note_ids, "intent": "rewrite"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["created_count"] == 2
        assert [item["title"] for item in payload["items"]] == ["First source", "Second source"]
        assert [item["body"] for item in payload["items"]] == ["First body", "Second body"]
        assert [item["source_note_id"] for item in payload["items"]] == note_ids

        intruder_response = client.post(
            "/api/notes/batch-create-drafts",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"note_ids": [note_ids[0]], "intent": "rewrite"},
        )
        assert intruder_response.status_code == 404
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_notes_export_writes_json_for_owned_notes_and_rejects_cross_user_notes(tmp_path):
    import json
    from pathlib import Path

    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "notes-export-owner")
    intruder_token = _register_and_get_access_token("notes-export-intruder")
    try:
        save_response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "account_id": owner_account_id,
                "notes": [
                    {
                        "note_id": "export-note-001",
                        "title": "Exported note",
                        "content": "Export body",
                        "author_name": "Export author",
                        "raw": {"source": "unit-test"},
                    }
                ],
            },
        )
        assert save_response.status_code == 200
        note_id = save_response.json()["items"][0]["id"]
        tag_response = client.post(
            "/api/tags",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"name": "Export", "color": "#111111"},
        )
        client.post(
            "/api/notes/batch-tag",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"note_ids": [note_id], "tag_ids": [tag_response.json()["id"]], "mode": "replace"},
        )

        response = client.post(
            "/api/notes/export",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"note_ids": [note_id], "format": "json"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["exported_count"] == 1
        assert payload["file_name"].endswith(".json")
        assert f"u{1}-" in payload["file_name"]
        export_path = Path(payload["file_path"])
        assert export_path.exists()
        exported = json.loads(export_path.read_text(encoding="utf-8"))
        assert exported["items"][0]["note_id"] == "export-note-001"
        assert exported["items"][0]["tags"][0]["name"] == "Export"

        download_response = client.get(
            payload["download_url"],
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert download_response.status_code == 200
        assert download_response.json()["items"][0]["note_id"] == "export-note-001"

        intruder_download_response = client.get(
            payload["download_url"],
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_download_response.status_code == 404

        intruder_response = client.post(
            "/api/notes/export",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"note_ids": [note_id], "format": "json"},
        )
        assert intruder_response.status_code == 404
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_notes_export_writes_csv_for_owned_notes(tmp_path):
    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "notes-export-csv-owner")
    try:
        save_response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "account_id": owner_account_id,
                "notes": [
                    {
                        "note_id": "export-csv-001",
                        "title": "CSV 标题",
                        "content": "CSV 正文",
                        "author_name": "CSV 作者",
                    }
                ],
            },
        )
        note_id = save_response.json()["items"][0]["id"]

        response = client.post(
            "/api/notes/export",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"note_ids": [note_id], "format": "csv"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["file_name"].endswith(".csv")
        download_response = client.get(
            payload["download_url"],
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert download_response.status_code == 200
        csv_text = download_response.content.decode("utf-8-sig")
        assert "note_id,title,author_name,content,tags,created_at" in csv_text
        assert "export-csv-001" in csv_text
        assert "CSV 标题" in csv_text
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_xhs_analytics_uses_current_user_saved_notes_tags_and_comments(tmp_path):
    from backend.app.core.database import get_db
    from backend.app.models import NoteComment

    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "analytics-owner")
    intruder_token = _register_and_get_access_token("analytics-intruder")
    try:
        save_response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "account_id": owner_account_id,
                "notes": [
                    {
                        "note_id": "analytics-note-001",
                        "title": "高互动早餐笔记",
                        "content": "早餐选题正文",
                        "author_name": "早餐作者",
                        "raw": {"likes": 100, "collects": 30, "comments": 12, "shares": 8, "tags": ["早餐", "低卡"]},
                    },
                    {
                        "note_id": "analytics-note-002",
                        "title": "普通收纳笔记",
                        "content": "收纳正文",
                        "author_name": "收纳作者",
                        "raw": {"likes": 10, "collects": 2, "comments": 1, "shares": 0, "tags": ["收纳"]},
                    },
                ],
            },
        )
        assert save_response.status_code == 200
        first_note_id = save_response.json()["items"][0]["id"]
        tag_response = client.post(
            "/api/tags",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"name": "早餐", "color": "#111111"},
        )
        client.post(
            "/api/notes/batch-tag",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"note_ids": [first_note_id], "tag_ids": [tag_response.json()["id"]], "mode": "add"},
        )
        db = next(app.dependency_overrides[get_db]())
        try:
            db.add(
                NoteComment(
                    note_id=first_note_id,
                    comment_id="analytics-comment-001",
                    user_name="用户 A",
                    content="这个早餐适合通勤吗？价格会不会高？",
                    like_count=9,
                )
            )
            db.commit()
        finally:
            db.close()

        overview_response = client.get(
            "/api/xhs/analytics/overview",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert overview_response.status_code == 200
        overview = overview_response.json()
        assert overview["platform"] == "xhs"
        assert overview["saved_notes"] == 2
        assert overview["total_engagement"] == 163
        assert overview["comment_count"] == 1
        assert overview["hot_topics"][0]["keyword"] == "早餐"

        top_response = client.get(
            "/api/xhs/analytics/top-content",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert top_response.status_code == 200
        top_items = top_response.json()["items"]
        assert [item["note_id"] for item in top_items] == ["analytics-note-001", "analytics-note-002"]
        assert top_items[0]["engagement"] == 150

        topics_response = client.get(
            "/api/xhs/analytics/hot-topics",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert topics_response.status_code == 200
        topics = topics_response.json()["items"]
        assert topics[0]["keyword"] == "早餐"
        assert topics[0]["notes"] == 1
        assert topics[0]["engagement"] == 150

        comments_response = client.get(
            "/api/xhs/analytics/comment-insights",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert comments_response.status_code == 200
        comments = comments_response.json()
        assert comments["total_comments"] == 1
        assert comments["question_count"] == 1
        assert comments["top_comments"][0]["content"] == "这个早餐适合通勤吗？价格会不会高？"

        intruder_response = client.get(
            "/api/xhs/analytics/overview",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_response.status_code == 200
        assert intruder_response.json()["saved_notes"] == 0
        assert intruder_response.json()["total_engagement"] == 0
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_xhs_analytics_benchmarks_are_user_scoped_from_monitoring_targets(tmp_path):
    from backend.app.core.database import get_db
    from backend.app.models import MonitoringTarget

    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "benchmark-owner")
    intruder_token = _register_and_get_access_token("benchmark-intruder")
    try:
        anonymous_response = client.get("/api/xhs/analytics/benchmarks")
        assert anonymous_response.status_code == 401

        save_response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "account_id": owner_account_id,
                "notes": [
                    {
                        "note_id": "benchmark-note-account",
                        "title": "竞品账号低卡早餐",
                        "content": "creator-001 的早餐选题",
                        "author_name": "creator-001",
                        "raw": {"likes": 80, "collects": 12, "comments": 6, "shares": 2},
                    },
                    {
                        "note_id": "benchmark-note-brand",
                        "title": "BrandA 收纳爆文",
                        "content": "BrandA 新品收纳角度",
                        "author_name": "brand-author",
                        "raw": {"likes": 30, "collects": 10, "comments": 4, "shares": 1},
                    },
                    {
                        "note_id": "benchmark-note-keyword-only",
                        "title": "低卡早餐普通趋势",
                        "content": "低卡早餐关键词命中但不是竞品目标",
                        "author_name": "trend-author",
                        "raw": {"likes": 300},
                    },
                ],
            },
        )
        assert save_response.status_code == 200
        db = next(app.dependency_overrides[get_db]())
        try:
            db.add_all(
                [
                    MonitoringTarget(
                        user_id=1,
                        platform="xhs",
                        target_type="account",
                        name="竞品账号",
                        value="creator-001",
                        status="active",
                    ),
                    MonitoringTarget(
                        user_id=1,
                        platform="xhs",
                        target_type="brand",
                        name="BrandA",
                        value="BrandA",
                        status="active",
                    ),
                    MonitoringTarget(
                        user_id=1,
                        platform="xhs",
                        target_type="keyword",
                        name="低卡早餐",
                        value="低卡早餐",
                        status="active",
                    ),
                    MonitoringTarget(
                        user_id=2,
                        platform="xhs",
                        target_type="account",
                        name="Other account",
                        value="creator-001",
                        status="active",
                    ),
                ]
            )
            db.commit()
        finally:
            db.close()

        response = client.get(
            "/api/xhs/analytics/benchmarks",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["total_targets"] == 2
        assert payload["matched_notes"] == 2
        assert payload["total_engagement"] == 145
        assert [item["target_type"] for item in payload["items"]] == ["account", "brand"]
        assert payload["items"][0]["name"] == "竞品账号"
        assert payload["items"][0]["matched_notes"] == 1
        assert payload["items"][0]["total_engagement"] == 100
        assert payload["items"][0]["top_notes"][0]["note_id"] == "benchmark-note-account"
        assert payload["items"][1]["name"] == "BrandA"
        assert payload["items"][1]["total_engagement"] == 45

        intruder_response = client.get(
            "/api/xhs/analytics/benchmarks",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_response.status_code == 200
        assert intruder_response.json()["total_targets"] == 1
        assert intruder_response.json()["matched_notes"] == 0
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_xhs_benchmark_create_drafts_uses_owned_target_matches(tmp_path):
    from backend.app.core.database import get_db
    from backend.app.models import AiDraft, MonitoringTarget

    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "benchmark-draft-owner")
    intruder_token = _register_and_get_access_token("benchmark-draft-intruder")
    try:
        save_response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "account_id": owner_account_id,
                "notes": [
                    {
                        "note_id": "benchmark-draft-note-001",
                        "title": "creator-002 爆款标题",
                        "content": "creator-002 的爆款正文",
                        "author_name": "creator-002",
                        "raw": {"likes": 90},
                    },
                    {
                        "note_id": "benchmark-draft-note-002",
                        "title": "creator-002 第二篇",
                        "content": "creator-002 的第二篇正文",
                        "author_name": "creator-002",
                        "raw": {"likes": 40},
                    },
                    {
                        "note_id": "benchmark-draft-note-other",
                        "title": "其他账号内容",
                        "content": "不该命中",
                        "author_name": "other",
                        "raw": {"likes": 500},
                    },
                ],
            },
        )
        assert save_response.status_code == 200
        db = next(app.dependency_overrides[get_db]())
        try:
            target = MonitoringTarget(
                user_id=1,
                platform="xhs",
                target_type="account",
                name="creator-002",
                value="creator-002",
                status="active",
            )
            keyword_target = MonitoringTarget(
                user_id=1,
                platform="xhs",
                target_type="keyword",
                name="普通关键词",
                value="creator-002",
                status="active",
            )
            intruder_target = MonitoringTarget(
                user_id=2,
                platform="xhs",
                target_type="account",
                name="intruder target",
                value="creator-002",
                status="active",
            )
            db.add_all([target, keyword_target, intruder_target])
            db.commit()
            target_id = target.id
            keyword_target_id = keyword_target.id
        finally:
            db.close()

        anonymous_response = client.post(f"/api/xhs/analytics/benchmarks/{target_id}/create-drafts")
        assert anonymous_response.status_code == 401

        intruder_response = client.post(
            f"/api/xhs/analytics/benchmarks/{target_id}/create-drafts",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_response.status_code == 404

        keyword_response = client.post(
            f"/api/xhs/analytics/benchmarks/{keyword_target_id}/create-drafts",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert keyword_response.status_code == 400

        response = client.post(
            f"/api/xhs/analytics/benchmarks/{target_id}/create-drafts?limit=1",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["created_count"] == 1
        assert payload["items"][0]["title"] == "creator-002 爆款标题"
        assert payload["items"][0]["source_note_id"] == save_response.json()["items"][0]["id"]

        db = next(app.dependency_overrides[get_db]())
        try:
            drafts = db.query(AiDraft).all()
            assert len(drafts) == 1
            assert drafts[0].user_id == 1
            assert drafts[0].platform == "xhs"
            assert drafts[0].body == "creator-002 的爆款正文"
        finally:
            db.close()
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_xhs_analytics_report_generates_owned_json_export_and_rejects_cross_user_notes(tmp_path):
    import json
    from pathlib import Path

    from backend.app.core.database import get_db
    from backend.app.models import PlatformAccount

    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "analytics-report-owner")
    intruder_token = _register_and_get_access_token("analytics-report-intruder")
    try:
        anonymous_response = client.post("/api/xhs/analytics/reports")
        assert anonymous_response.status_code == 401

        owner_save_response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "account_id": owner_account_id,
                "notes": [
                    {
                        "note_id": "analytics-report-note-001",
                        "title": "Report note one",
                        "content": "Breakfast content with BrandA",
                        "author_name": "creator-report",
                        "raw": {"likes": 20, "collects": 5, "comments": 3, "shares": 2, "tags": ["breakfast"]},
                    },
                    {
                        "note_id": "analytics-report-note-002",
                        "title": "Report note two",
                        "content": "Storage content",
                        "author_name": "creator-report",
                        "raw": {"likes": 10, "collects": 1, "comments": 0, "shares": 0, "tags": ["storage"]},
                    },
                ],
            },
        )
        assert owner_save_response.status_code == 200
        owner_note_ids = [item["id"] for item in owner_save_response.json()["items"]]

        db = next(app.dependency_overrides[get_db]())
        try:
            intruder_account = PlatformAccount(
                user_id=2,
                platform="xhs",
                sub_type="pc",
                external_user_id="analytics-report-intruder",
                nickname="Intruder",
                status="active",
            )
            db.add(intruder_account)
            db.commit()
            intruder_account_id = intruder_account.id
        finally:
            db.close()

        intruder_save_response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={
                "account_id": intruder_account_id,
                "notes": [
                    {
                        "note_id": "analytics-report-intruder-note",
                        "title": "Intruder note",
                        "content": "Not visible to owner",
                        "author_name": "intruder",
                        "raw": {"likes": 999},
                    }
                ],
            },
        )
        assert intruder_save_response.status_code == 200
        intruder_note_id = intruder_save_response.json()["items"][0]["id"]

        forbidden_response = client.post(
            "/api/xhs/analytics/reports",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"note_ids": [owner_note_ids[0], intruder_note_id], "format": "json"},
        )
        assert forbidden_response.status_code == 404

        report_response = client.post(
            "/api/xhs/analytics/reports",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"note_ids": owner_note_ids, "format": "json"},
        )
        assert report_response.status_code == 200
        report = report_response.json()
        assert report["report_type"] == "operations"
        assert report["note_count"] == 2
        assert report["summary"]["total_engagement"] == 41
        assert report["summary"]["top_notes"][0]["note_id"] == "analytics-report-note-001"
        assert report["file_name"].startswith("xhs-report-u1-")
        assert report["download_url"].startswith("/api/files/exports/xhs-report-u1-")

        report_path = Path(report["file_path"])
        assert report_path.is_file()
        report_file = json.loads(report_path.read_text(encoding="utf-8"))
        assert report_file["metadata"]["user_id"] == 1
        assert report_file["summary"]["note_count"] == 2
        assert report_file["top_notes"][0]["title"] == "Report note one"

        download_response = client.get(
            report["download_url"],
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert download_response.status_code == 200
        assert download_response.json()["metadata"]["report_type"] == "operations"

        intruder_download_response = client.get(
            report["download_url"],
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_download_response.status_code == 404
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_xhs_crawl_routes_are_authenticated_task_backed_and_persist_notes(tmp_path):
    from backend.app.api.platforms.xhs.pc import get_xhs_pc_api_adapter_factory
    from backend.app.core.database import get_db
    from backend.app.models import Note, NoteAsset, Task

    class FakeCrawlAdapter:
        def __init__(self, cookies):
            self.cookies = cookies

        def search_note(self, keyword, page=1, **kwargs):
            return True, "ok", {
                "data": {
                    "items": [
                        {
                            "note_card": {
                                "note_id": "crawl-search-001",
                                "display_title": f"{keyword} search title",
                                "desc": "search content",
                                "user": {"nickname": "search author"},
                                "interact_info": {"liked_count": 12, "collected_count": 3, "comment_count": 2},
                                "cover": {"url": "https://img.example/search.png"},
                            }
                        }
                    ],
                    "total": 1,
                    "has_more": False,
                }
            }

        def get_note_info(self, url):
            return True, "ok", {
                "data": {
                    "items": [
                        {
                            "note_card": {
                                "note_id": "crawl-url-001",
                                "display_title": "url detail title",
                                "desc": "url detail body",
                                "user": {"nickname": "url author"},
                                "interact_info": {"liked_count": 30},
                                "image_list": [{"url": "https://img.example/url-1.png"}],
                            }
                        }
                    ]
                }
            }

        def get_user_notes(self, user_url):
            return True, "ok", {
                "data": {
                    "items": [
                        {
                            "note_card": {
                                "note_id": "crawl-user-001",
                                "display_title": "user note title",
                                "desc": "user note body",
                                "user": {"nickname": "profile author"},
                                "interact_info": {"liked_count": 7},
                                "cover": {"url": "https://img.example/user.png"},
                            }
                        }
                    ],
                    "total": 1,
                }
            }

    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "crawl-routes-owner")
    intruder_token = _register_and_get_access_token("crawl-routes-intruder")
    app.dependency_overrides[get_xhs_pc_api_adapter_factory] = lambda: FakeCrawlAdapter
    try:
        anonymous_response = client.post(
            "/api/xhs/crawl/search-notes",
            json={"account_id": owner_account_id, "keyword": "breakfast"},
        )
        assert anonymous_response.status_code == 401

        intruder_response = client.post(
            "/api/xhs/crawl/search-notes",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"account_id": owner_account_id, "keyword": "breakfast"},
        )
        assert intruder_response.status_code == 404

        search_response = client.post(
            "/api/xhs/crawl/search-notes",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"account_id": owner_account_id, "keyword": "breakfast", "page": 1},
        )
        assert search_response.status_code == 200
        search_payload = search_response.json()
        assert search_payload["task"]["task_type"] == "crawl"
        assert search_payload["task"]["status"] == "completed"
        assert search_payload["saved_count"] == 1
        assert search_payload["items"][0]["note_id"] == "crawl-search-001"

        url_response = client.post(
            "/api/xhs/crawl/note-urls",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"account_id": owner_account_id, "urls": ["https://www.xiaohongshu.com/explore/crawl-url-001"]},
        )
        assert url_response.status_code == 200
        assert url_response.json()["saved_count"] == 1
        assert url_response.json()["items"][0]["note_id"] == "crawl-url-001"

        user_response = client.post(
            "/api/xhs/crawl/user-notes",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"account_id": owner_account_id, "user_url": "https://www.xiaohongshu.com/user/profile/demo"},
        )
        assert user_response.status_code == 200
        assert user_response.json()["saved_count"] == 1
        assert user_response.json()["items"][0]["note_id"] == "crawl-user-001"

        db = next(app.dependency_overrides[get_db]())
        try:
            tasks = db.query(Task).filter(Task.task_type == "crawl").all()
            notes = db.query(Note).order_by(Note.note_id.asc()).all()
            assets = db.query(NoteAsset).all()
            assert len(tasks) == 3
            assert all(task.user_id == 1 and task.status == "completed" for task in tasks)
            assert [note.note_id for note in notes] == ["crawl-search-001", "crawl-url-001", "crawl-user-001"]
            assert len(assets) == 3
        finally:
            db.close()
    finally:
        app.dependency_overrides.pop(get_xhs_pc_api_adapter_factory, None)
        app.dependency_overrides.pop(db_dependency, None)


def test_xhs_data_crawl_marks_partial_failures_and_fetches_comments(tmp_path):
    from backend.app.api.platforms.xhs.pc import get_xhs_pc_api_adapter_factory

    class FakeDataCrawlAdapter:
        calls = []

        def __init__(self, cookies):
            self.cookies = cookies

        def get_note_info(self, url):
            self.__class__.calls.append(("detail", url))
            if "bad" in url:
                return False, "detail failed", {}
            return True, "ok", {
                "data": {
                    "items": [
                        {
                            "note_card": {
                                "note_id": "data-url-001",
                                "display_title": "data crawl detail",
                                "desc": "detail body",
                                "user": {"nickname": "detail author"},
                                "interact_info": {"liked_count": 8, "comment_count": 1},
                                "image_list": [{"url": "https://img.example/data-url.png"}],
                            }
                        }
                    ]
                }
            }

        def get_note_comments(self, url):
            self.__class__.calls.append(("comments", url))
            return True, "ok", {
                "data": {
                    "comments": [
                        {
                            "id": "comment-001",
                            "content": "想看更多",
                            "user_info": {"nickname": "reader"},
                            "like_count": "3",
                        }
                    ]
                }
            }

    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "data-crawl-owner")
    FakeDataCrawlAdapter.calls = []
    app.dependency_overrides[get_xhs_pc_api_adapter_factory] = lambda: FakeDataCrawlAdapter
    try:
        response = client.post(
            "/api/xhs/crawl/data",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "account_id": owner_account_id,
                "mode": "note_urls",
                "urls": [
                    "https://www.xiaohongshu.com/explore/data-url-001",
                    "https://www.xiaohongshu.com/explore/bad-url",
                ],
                "fetch_comments": True,
            },
        )

        assert response.status_code == 200
        payload = _parse_sse_response(response)
        assert payload["total"] == 2
        assert payload["success_count"] == 1
        assert payload["failed_count"] == 1
        assert payload["items"][0]["status"] == "success"
        assert payload["items"][0]["note"]["note_id"] == "data-url-001"
        assert payload["items"][0]["comment_count"] == 1
        assert payload["items"][0]["comments"][0]["content"] == "想看更多"
        assert payload["items"][1]["status"] == "failed"
        assert payload["items"][1]["error"] == "detail failed"
        assert ("comments", "https://www.xiaohongshu.com/explore/data-url-001") in FakeDataCrawlAdapter.calls
    finally:
        app.dependency_overrides.pop(get_xhs_pc_api_adapter_factory, None)
        app.dependency_overrides.pop(db_dependency, None)


def test_xhs_data_crawl_search_expands_filters_and_fetches_details(tmp_path):
    from backend.app.api.platforms.xhs.pc import get_xhs_pc_api_adapter_factory

    class FakeSearchDataCrawlAdapter:
        search_calls = []
        detail_calls = []

        def __init__(self, cookies):
            self.cookies = cookies

        def search_note(self, keyword, page=1, **kwargs):
            self.__class__.search_calls.append({"keyword": keyword, "page": page, **kwargs})
            return True, "ok", {
                "data": {
                    "has_more": False,
                    "items": [
                        {
                            "xsec_token": "xsec-data-search",
                            "note_card": {
                                "note_id": "data-search-001",
                                "display_title": "search source title",
                                "desc": "search source body",
                                "user": {"nickname": "search author"},
                                "interact_info": {"liked_count": 12},
                                "cover": {"url": "https://img.example/search.png"},
                            },
                        }
                    ],
                }
            }

        def get_note_info(self, url):
            self.__class__.detail_calls.append(url)
            return True, "ok", {
                "data": {
                    "items": [
                        {
                            "note_card": {
                                "note_id": "data-search-001",
                                "display_title": "detail title",
                                "desc": "detail body",
                                "user": {"nickname": "detail author"},
                                "interact_info": {"liked_count": 88},
                                "image_list": [{"url": "https://img.example/detail.png"}],
                            }
                        }
                    ]
                }
            }

    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "data-crawl-search-owner")
    FakeSearchDataCrawlAdapter.search_calls = []
    FakeSearchDataCrawlAdapter.detail_calls = []
    app.dependency_overrides[get_xhs_pc_api_adapter_factory] = lambda: FakeSearchDataCrawlAdapter
    try:
        response = client.post(
            "/api/xhs/crawl/data",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "account_id": owner_account_id,
                "mode": "search",
                "keyword": "低卡早餐",
                "pages": 1,
                "max_notes": 5,
                "sort_type_choice": 2,
                "note_type": 2,
                "note_time": 1,
                "note_range": 3,
                "pos_distance": 1,
                "geo": "31.2304,121.4737",
            },
        )

        assert response.status_code == 200
        payload = _parse_sse_response(response)
        assert payload["success_count"] == 1
        assert payload["items"][0]["note"]["title"] == "detail title"
        assert FakeSearchDataCrawlAdapter.search_calls == [
            {
                "keyword": "低卡早餐",
                "page": 1,
                "sort_type_choice": 2,
                "note_type": 2,
                "note_time": 1,
                "note_range": 3,
                "pos_distance": 1,
                "geo": "31.2304,121.4737",
            }
        ]
        assert FakeSearchDataCrawlAdapter.detail_calls == [
            "https://www.xiaohongshu.com/explore/data-search-001?xsec_token=xsec-data-search&xsec_source=pc_feed"
        ]
    finally:
        app.dependency_overrides.pop(get_xhs_pc_api_adapter_factory, None)
        app.dependency_overrides.pop(db_dependency, None)


def test_xhs_analytics_keyword_trends_are_user_scoped_from_keyword_groups(tmp_path):
    from backend.app.core.database import get_db
    from backend.app.models import KeywordGroup

    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "keyword-trends-owner")
    intruder_token = _register_and_get_access_token("keyword-trends-intruder")
    try:
        anonymous_response = client.get("/api/xhs/analytics/keyword-trends")
        assert anonymous_response.status_code == 401

        save_response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "account_id": owner_account_id,
                "notes": [
                    {
                        "note_id": "keyword-trend-note-001",
                        "title": "Breakfast angle",
                        "content": "Low calorie breakfast for commute",
                        "author_name": "trend author",
                        "raw": {"likes": 20, "collects": 5, "comments": 1, "shares": 0},
                    },
                    {
                        "note_id": "keyword-trend-note-002",
                        "title": "Storage angle",
                        "content": "Closet storage checklist",
                        "author_name": "trend author",
                        "raw": {"likes": 10, "collects": 2},
                    },
                ],
            },
        )
        assert save_response.status_code == 200

        db = next(app.dependency_overrides[get_db]())
        try:
            db.add_all(
                [
                    KeywordGroup(user_id=1, platform="xhs", name="Owner ideas", keywords=["breakfast", "storage"]),
                    KeywordGroup(user_id=2, platform="xhs", name="Intruder ideas", keywords=["breakfast"]),
                ]
            )
            db.commit()
        finally:
            db.close()

        owner_response = client.get(
            "/api/xhs/analytics/keyword-trends",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert owner_response.status_code == 200
        owner_items = owner_response.json()["items"]
        assert [item["keyword"] for item in owner_items] == ["breakfast", "storage"]
        assert owner_items[0]["group_name"] == "Owner ideas"
        assert owner_items[0]["notes"] == 1
        assert owner_items[0]["engagement"] == 26
        assert owner_items[0]["top_notes"][0]["note_id"] == "keyword-trend-note-001"
        assert owner_items[1]["engagement"] == 12

        intruder_response = client.get(
            "/api/xhs/analytics/keyword-trends",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_response.status_code == 200
        assert intruder_response.json()["items"][0]["keyword"] == "breakfast"
        assert intruder_response.json()["items"][0]["notes"] == 0
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_xhs_creator_routes_use_owned_creator_account_and_record_tasks(tmp_path):
    from backend.app.api.platforms.xhs.creator import get_creator_api_adapter_factory
    from backend.app.core.database import get_db
    from backend.app.models import Task

    class FakeCreatorRoutesAdapter:
        def __init__(self, cookies):
            self.cookies = cookies

        def get_topic(self, keyword):
            return True, "ok", {"data": {"items": [{"id": "topic-creator", "name": keyword}]}}

        def get_location_info(self, keyword):
            return True, "ok", {"data": {"items": [{"id": "loc-creator", "name": keyword}]}}

        def upload_media(self, file_path, media_type):
            return {"fileIds": "file-creator-001", "width": 1080, "height": 1440, "media_type": media_type}

        def post_note(self, note_info):
            return {"success": True, "data": {"note_id": "creator-direct-note"}, "note_info": note_info}

        def get_published_notes(self):
            return True, "ok", {"data": {"items": [{"note_id": "published-001", "title": "Published"}]}}

    db_dependency, owner_token, creator_account_id = _create_creator_account_with_cookie(
        tmp_path, "creator-routes-owner"
    )
    intruder_token = _register_and_get_access_token("creator-routes-intruder")
    app.dependency_overrides[get_creator_api_adapter_factory] = lambda: FakeCreatorRoutesAdapter
    try:
        anonymous_response = client.post(
            "/api/xhs/creator/topics/search",
            json={"account_id": creator_account_id, "keyword": "breakfast"},
        )
        assert anonymous_response.status_code == 401

        intruder_response = client.post(
            "/api/xhs/creator/topics/search",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"account_id": creator_account_id, "keyword": "breakfast"},
        )
        assert intruder_response.status_code == 404

        topic_response = client.post(
            "/api/xhs/creator/topics/search",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"account_id": creator_account_id, "keyword": "breakfast"},
        )
        assert topic_response.status_code == 200
        assert topic_response.json()["items"][0]["name"] == "breakfast"

        location_response = client.post(
            "/api/xhs/creator/locations/search",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"account_id": creator_account_id, "keyword": "Shanghai"},
        )
        assert location_response.status_code == 200
        assert location_response.json()["items"][0]["id"] == "loc-creator"

        upload_response = client.post(
            "/api/xhs/creator/assets/upload",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"account_id": creator_account_id, "file_path": "storage/media/cover.png", "media_type": "image"},
        )
        assert upload_response.status_code == 200
        assert upload_response.json()["payload"]["fileIds"] == "file-creator-001"
        assert upload_response.json()["task"]["task_type"] == "creator_direct_upload"

        publish_response = client.post(
            "/api/xhs/creator/publish/image",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "account_id": creator_account_id,
                "title": "Direct title",
                "body": "Direct body",
                "image_file_infos": [{"fileIds": "file-creator-001", "width": 1080, "height": 1440}],
            },
        )
        assert publish_response.status_code == 200
        assert publish_response.json()["payload"]["data"]["note_id"] == "creator-direct-note"
        assert publish_response.json()["task"]["task_type"] == "creator_direct_publish"

        video_response = client.post(
            "/api/xhs/creator/publish/video",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "account_id": creator_account_id,
                "title": "Video title",
                "body": "Video body",
                "video_info": {"video_id": "video-001"},
            },
        )
        assert video_response.status_code == 200
        assert video_response.json()["payload"]["note_info"]["media_type"] == "video"

        published_response = client.get(
            f"/api/xhs/creator/published?account_id={creator_account_id}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert published_response.status_code == 200
        assert published_response.json()["items"][0]["note_id"] == "published-001"

        db = next(app.dependency_overrides[get_db]())
        try:
            tasks = db.query(Task).filter(Task.task_type.in_(["creator_direct_upload", "creator_direct_publish"])).all()
            assert [task.status for task in tasks] == ["completed", "completed", "completed"]
            assert all(task.user_id == 1 for task in tasks)
        finally:
            db.close()
    finally:
        app.dependency_overrides.pop(get_creator_api_adapter_factory, None)
        app.dependency_overrides.pop(db_dependency, None)


def test_xhs_creator_direct_publish_accepts_optional_publish_parameters(tmp_path):
    from backend.app.api.platforms.xhs.creator import get_creator_api_adapter_factory

    class FakeCreatorOptionalAdapter:
        calls = []

        def __init__(self, cookies):
            self.cookies = cookies

        def post_note(self, note_info):
            self.calls.append({"cookies": self.cookies, "note_info": note_info})
            return {"success": True, "data": {"note_id": "optional-note"}, "note_info": note_info}

    db_dependency, owner_token, creator_account_id = _create_creator_account_with_cookie(
        tmp_path, "creator-optional-owner"
    )
    FakeCreatorOptionalAdapter.calls = []
    app.dependency_overrides[get_creator_api_adapter_factory] = lambda: FakeCreatorOptionalAdapter
    try:
        image_response = client.post(
            "/api/xhs/creator/publish/image",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "account_id": creator_account_id,
                "title": "Direct optional title",
                "image_file_infos": [{"fileIds": "file-optional", "width": 1080, "height": 1440}],
                "topics": ["早餐", "通勤"],
                "location": "上海",
                "is_private": False,
            },
        )

        assert image_response.status_code == 200
        assert FakeCreatorOptionalAdapter.calls == [
            {
                "cookies": "web_session=creator-session; a1=creator-a1",
                "note_info": {
                    "title": "Direct optional title",
                    "desc": "",
                    "media_type": "image",
                    "image_file_infos": [{"fileIds": "file-optional", "width": 1080, "height": 1440}],
                    "type": 0,
                    "postTime": None,
                    "topics": ["早餐", "通勤"],
                    "location": "上海",
                },
            }
        ]
    finally:
        app.dependency_overrides.pop(get_creator_api_adapter_factory, None)
        app.dependency_overrides.pop(db_dependency, None)


def test_monitoring_targets_crud_are_user_scoped(tmp_path):
    db_dependency = _override_database(tmp_path)
    owner_token = _register_and_get_access_token("monitoring-owner")
    intruder_token = _register_and_get_access_token("monitoring-intruder")
    try:
        anonymous_response = client.get("/api/xhs/monitoring/targets")
        assert anonymous_response.status_code == 401

        create_response = client.post(
            "/api/xhs/monitoring/targets",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "target_type": "keyword",
                "name": "早餐趋势",
                "value": "低卡早餐",
                "config": {"frequency": "daily"},
            },
        )
        assert create_response.status_code == 200
        created = create_response.json()
        assert created["target_type"] == "keyword"
        assert created["name"] == "早餐趋势"
        assert created["value"] == "低卡早餐"
        assert created["status"] == "active"

        owner_list_response = client.get(
            "/api/xhs/monitoring/targets",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert owner_list_response.status_code == 200
        assert owner_list_response.json()["total"] == 1

        intruder_list_response = client.get(
            "/api/xhs/monitoring/targets",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_list_response.status_code == 200
        assert intruder_list_response.json()["total"] == 0

        update_response = client.patch(
            f"/api/xhs/monitoring/targets/{created['id']}",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"name": "早餐趋势组", "status": "paused"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "早餐趋势组"
        assert update_response.json()["status"] == "paused"

        intruder_update_response = client.patch(
            f"/api/xhs/monitoring/targets/{created['id']}",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"name": "偷看"},
        )
        assert intruder_update_response.status_code == 404

        delete_response = client.delete(
            f"/api/xhs/monitoring/targets/{created['id']}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert delete_response.status_code == 200
        assert delete_response.json() == {"id": created["id"], "status": "deleted"}
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_monitoring_targets_refresh_creates_owned_task(tmp_path):
    from backend.app.api.platforms.xhs.pc import get_xhs_pc_api_adapter_factory

    class FakeMonitoringAdapter:
        def __init__(self, cookies):
            self.cookies = cookies

        def get_user_notes(self, user_url):
            return True, "ok", {
                "data": {
                    "items": [
                        {
                            "note_card": {
                                "note_id": "crawled-note-001",
                                "display_title": "竞品账号低卡早餐",
                                "desc": "creator-001 的早餐选题",
                                "user": {"nickname": "creator-001"},
                                "interact_info": {"liked_count": 50, "collected_count": 20, "comment_count": 3},
                                "cover": {"url": "https://img.example/cover.png"},
                            }
                        }
                    ],
                    "total": 1,
                    "has_more": False,
                }
            }

    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "monitoring-refresh-owner")
    intruder_token = _register_and_get_access_token("monitoring-refresh-intruder")
    app.dependency_overrides[get_xhs_pc_api_adapter_factory] = lambda: FakeMonitoringAdapter
    try:
        created = client.post(
            "/api/xhs/monitoring/targets",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"target_type": "account", "name": "竞品账号", "value": "creator-001"},
        ).json()

        refresh_response = client.post(
            f"/api/xhs/monitoring/targets/{created['id']}/refresh",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert refresh_response.status_code == 200
        payload = refresh_response.json()
        assert payload["target"]["id"] == created["id"]
        assert payload["task"]["task_type"] == "monitoring_crawl"
        assert payload["task"]["status"] == "completed"
        assert payload["task"]["payload"]["target_id"] == created["id"]
        assert payload["task"]["payload"]["crawled_count"] == 1
        assert payload["snapshot"]["payload"]["matched_count"] >= 1
        assert payload["snapshot"]["payload"]["top_notes"][0]["note_id"] == "crawled-note-001"
        assert payload["target"]["consecutive_failures"] == 0

        tasks_response = client.get(
            "/api/tasks?platform=xhs",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert tasks_response.status_code == 200
        assert tasks_response.json()["items"][0]["task_type"] == "monitoring_crawl"

        notes_response = client.get(
            f"/api/xhs/monitoring/targets/{created['id']}/notes",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert notes_response.status_code == 200
        assert len(notes_response.json()["items"]) >= 1

        snapshots_response = client.get(
            f"/api/xhs/monitoring/targets/{created['id']}/snapshots",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert snapshots_response.status_code == 200
        assert snapshots_response.json()["items"][0]["payload"]["matched_count"] >= 1

        intruder_response = client.post(
            f"/api/xhs/monitoring/targets/{created['id']}/refresh",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_xhs_pc_api_adapter_factory, None)
        app.dependency_overrides.pop(db_dependency, None)


def test_crawl_rate_limiter_blocks_after_max_requests():
    from backend.app.services.rate_limiter import CrawlRateLimiter

    limiter = CrawlRateLimiter(max_per_minute=3)
    assert limiter.allow(1) is True
    assert limiter.allow(1) is True
    assert limiter.allow(1) is True
    assert limiter.allow(1) is False

    assert limiter.allow(2) is True

    limiter.reset(1)
    assert limiter.allow(1) is True


def test_keyword_groups_require_authentication(tmp_path):
    db_dependency = _override_database(tmp_path)
    try:
        response = client.get("/api/keyword-groups")

        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_keyword_groups_crud_are_user_scoped(tmp_path):
    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "keyword-group-owner")
    intruder_token = _register_and_get_access_token("keyword-group-intruder")
    try:
        save_response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "account_id": owner_account_id,
                "notes": [
                    {
                        "note_id": "keyword-note-001",
                        "title": "低卡早餐模板",
                        "content": "适合通勤的低卡早餐搭配。",
                        "author_name": "早餐作者",
                        "raw": {"likes": 30, "collects": 10, "comments": 4, "shares": 1, "tags": ["低卡", "早餐"]},
                    },
                    {
                        "note_id": "keyword-note-002",
                        "title": "家居收纳灵感",
                        "content": "收纳工具清单。",
                        "author_name": "收纳作者",
                        "raw": {"likes": 2, "collects": 1, "comments": 0, "shares": 0, "tags": ["收纳"]},
                    },
                ],
            },
        )
        assert save_response.status_code == 200

        create_response = client.post(
            "/api/keyword-groups",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform": "xhs", "name": "早餐机会", "keywords": ["低卡", "早餐"]},
        )
        assert create_response.status_code == 200
        created = create_response.json()
        assert created["name"] == "早餐机会"
        assert created["keywords"] == ["低卡", "早餐"]

        owner_list_response = client.get("/api/keyword-groups", headers={"Authorization": f"Bearer {owner_token}"})
        assert owner_list_response.status_code == 200
        assert owner_list_response.json()["total"] == 1

        intruder_list_response = client.get("/api/keyword-groups", headers={"Authorization": f"Bearer {intruder_token}"})
        assert intruder_list_response.status_code == 200
        assert intruder_list_response.json()["total"] == 0

        detail_response = client.get(
            f"/api/keyword-groups/{created['id']}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert detail_response.status_code == 200
        detail = detail_response.json()
        assert detail["trend"]["total_matches"] == 1
        assert detail["trend"]["total_engagement"] == 45
        assert detail["trend"]["keywords"][0]["keyword"] == "低卡"
        assert detail["trend"]["matched_notes"][0]["note_id"] == "keyword-note-001"

        patch_response = client.patch(
            f"/api/keyword-groups/{created['id']}",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"name": "早餐选题池", "keywords": ["早餐"]},
        )
        assert patch_response.status_code == 200
        assert patch_response.json()["name"] == "早餐选题池"
        assert patch_response.json()["keywords"] == ["早餐"]

        cross_get_response = client.get(
            f"/api/keyword-groups/{created['id']}",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert cross_get_response.status_code == 404

        cross_patch_response = client.patch(
            f"/api/keyword-groups/{created['id']}",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"name": "偷看"},
        )
        assert cross_patch_response.status_code == 404

        delete_response = client.delete(
            f"/api/keyword-groups/{created['id']}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert delete_response.status_code == 200
        assert delete_response.json()["status"] == "deleted"
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_notes_batch_save_rejects_cross_user_account(tmp_path):
    db_dependency, _, account_id = _create_pc_account_with_cookie(tmp_path, "save-owner-2")
    intruder_token = _register_and_get_access_token("save-intruder")
    try:
        response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"account_id": account_id, "notes": [{"note_id": "note-001", "title": "标题"}]},
        )

        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_notes_library_list_requires_authentication(tmp_path):
    db_dependency = _override_database(tmp_path)
    try:
        response = client.get("/api/notes?platform=xhs")

        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_notes_library_list_returns_only_current_user_saved_notes(tmp_path):
    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "library-owner")
    intruder_token = _register_and_get_access_token("library-intruder")
    try:
        owner_save_response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "account_id": owner_account_id,
                "notes": [
                    {
                        "note_id": "owner-note-001",
                        "title": "我的内容库笔记",
                        "content": "这条应该只属于 owner。",
                        "author_name": "作者 Owner",
                        "raw": {"source": "owner"},
                    }
                ],
            },
        )
        assert owner_save_response.status_code == 200

        intruder_response = client.get(
            "/api/notes?platform=xhs",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_response.status_code == 200
        assert intruder_response.json()["total"] == 0

        owner_response = client.get(
            "/api/notes?platform=xhs",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert owner_response.status_code == 200
        payload = owner_response.json()
        assert payload["total"] == 1
        assert payload["page"] == 1
        assert payload["page_size"] == 20
        assert payload["items"][0]["note_id"] == "owner-note-001"
        assert payload["items"][0]["title"] == "我的内容库笔记"
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_notes_library_filters_by_keyword_tag_assets_and_comments(tmp_path):
    from backend.app.core.database import get_db
    from backend.app.models import NoteComment

    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "library-filter-owner")
    intruder_token = _register_and_get_access_token("library-filter-intruder")
    try:
        first_save = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "account_id": owner_account_id,
                "notes": [
                    {
                        "note_id": "filter-note-assets",
                        "title": "低卡早餐灵感",
                        "content": "适合通勤前快速准备。",
                        "author_name": "早餐研究员",
                        "image_urls": ["https://example.test/filter-assets.webp"],
                    },
                    {
                        "note_id": "filter-note-comments",
                        "title": "旅行收纳清单",
                        "content": "评论里有很多问题。",
                        "author_name": "收纳作者",
                    },
                ],
            },
        )
        assert first_save.status_code == 200
        asset_note_id = first_save.json()["items"][0]["id"]
        comment_note_id = first_save.json()["items"][1]["id"]

        tag_response = client.post(
            "/api/tags",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"name": "Breakfast", "color": "#111111"},
        )
        tag_id = tag_response.json()["id"]
        client.post(
            "/api/notes/batch-tag",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"note_ids": [asset_note_id], "tag_ids": [tag_id], "mode": "replace"},
        )
        db = next(app.dependency_overrides[get_db]())
        try:
            db.add(
                NoteComment(
                    note_id=comment_note_id,
                    comment_id="filter-comment-001",
                    user_name="评论用户",
                    content="这条笔记有评论",
                )
            )
            db.commit()
        finally:
            db.close()

        keyword_response = client.get(
            "/api/notes?platform=xhs&q=早餐",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert keyword_response.status_code == 200
        assert [item["note_id"] for item in keyword_response.json()["items"]] == ["filter-note-assets"]

        tag_filter_response = client.get(
            f"/api/notes?platform=xhs&tag_id={tag_id}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert tag_filter_response.status_code == 200
        assert [item["note_id"] for item in tag_filter_response.json()["items"]] == ["filter-note-assets"]

        assets_response = client.get(
            "/api/notes?platform=xhs&has_assets=true",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert assets_response.status_code == 200
        assert [item["note_id"] for item in assets_response.json()["items"]] == ["filter-note-assets"]

        comments_response = client.get(
            "/api/notes?platform=xhs&has_comments=true",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert comments_response.status_code == 200
        assert [item["note_id"] for item in comments_response.json()["items"]] == ["filter-note-comments"]

        intruder_response = client.get(
            f"/api/notes?platform=xhs&tag_id={tag_id}",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_response.status_code == 404
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_notes_library_detail_enforces_ownership(tmp_path):
    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "library-detail-owner")
    intruder_token = _register_and_get_access_token("library-detail-intruder")
    try:
        save_response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "account_id": owner_account_id,
                "notes": [
                    {
                        "note_id": "detail-note-001",
                        "title": "详情页笔记",
                        "content": "详情正文",
                        "author_name": "详情作者",
                        "raw": {"source": "detail"},
                    }
                ],
            },
        )
        note_id = save_response.json()["items"][0]["id"]

        owner_response = client.get(
            f"/api/notes/{note_id}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert owner_response.status_code == 200
        assert owner_response.json()["note_id"] == "detail-note-001"
        assert owner_response.json()["raw_json"] == {"source": "detail"}

        intruder_response = client.get(
            f"/api/notes/{note_id}",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_response.status_code == 404
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_notes_library_delete_removes_owned_note_children_and_rejects_cross_user(tmp_path):
    from backend.app.core.database import get_db
    from backend.app.models import AiDraft, Note, NoteAsset, NoteComment, Tag, note_tags

    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "library-delete-owner")
    intruder_token = _register_and_get_access_token("library-delete-intruder")
    try:
        db = next(app.dependency_overrides[get_db]())
        try:
            note = Note(
                user_id=1,
                platform_account_id=owner_account_id,
                platform="xhs",
                note_id="delete-note-001",
                title="Delete me",
            )
            tag = Tag(user_id=1, name="待删除", color="#111111")
            db.add_all([note, tag])
            db.flush()
            db.add(NoteAsset(note_id=note.id, asset_type="image", url="https://example.test/delete.webp"))
            db.add(NoteComment(note_id=note.id, comment_id="delete-comment", content="删除评论"))
            db.add(AiDraft(user_id=1, platform="xhs", title="Draft", body="Body", source_note_id=note.id))
            db.execute(note_tags.insert().values(note_id=note.id, tag_id=tag.id))
            db.commit()
            note_id = note.id
        finally:
            db.close()

        intruder_response = client.delete(
            f"/api/notes/{note_id}",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_response.status_code == 404

        owner_response = client.delete(
            f"/api/notes/{note_id}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert owner_response.status_code == 200
        assert owner_response.json() == {"id": note_id, "status": "deleted"}

        detail_response = client.get(
            f"/api/notes/{note_id}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert detail_response.status_code == 404

        db = next(app.dependency_overrides[get_db]())
        try:
            assert db.get(Note, note_id) is None
            assert db.query(NoteAsset).filter(NoteAsset.note_id == note_id).count() == 0
            assert db.query(NoteComment).filter(NoteComment.note_id == note_id).count() == 0
            assert db.execute(select(note_tags).where(note_tags.c.note_id == note_id)).first() is None
            assert db.query(AiDraft).filter(AiDraft.source_note_id == note_id).count() == 0
        finally:
            db.close()
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_drafts_api_requires_authentication(tmp_path):
    db_dependency = _override_database(tmp_path)
    try:
        response = client.post(
            "/api/drafts",
            json={"platform": "xhs", "title": "草稿标题", "body": "草稿正文"},
        )

        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_drafts_api_creates_from_owned_note_and_lists_current_user_only(tmp_path):
    from backend.app.core.database import get_db
    from backend.app.models import AiDraft

    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "draft-owner")
    intruder_token = _register_and_get_access_token("draft-intruder")
    try:
        save_response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "account_id": owner_account_id,
                "notes": [
                    {
                        "note_id": "draft-source-note",
                        "title": "源笔记标题",
                        "content": "源笔记正文",
                        "author_name": "源作者",
                        "raw": {"source": "draft"},
                    }
                ],
            },
        )
        source_note_id = save_response.json()["items"][0]["id"]

        create_response = client.post(
            "/api/drafts",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform": "xhs", "source_note_id": source_note_id, "intent": "rewrite"},
        )
        assert create_response.status_code == 200
        created = create_response.json()
        assert created["platform"] == "xhs"
        assert created["title"] == "源笔记标题"
        assert created["body"] == "源笔记正文"
        assert created["source_note_id"] == source_note_id

        owner_list_response = client.get(
            "/api/drafts?platform=xhs",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert owner_list_response.status_code == 200
        owner_payload = owner_list_response.json()
        assert owner_payload["total"] == 1
        assert owner_payload["items"][0]["id"] == created["id"]

        intruder_list_response = client.get(
            "/api/drafts?platform=xhs",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_list_response.status_code == 200
        assert intruder_list_response.json()["total"] == 0

        db = next(app.dependency_overrides[get_db]())
        try:
            draft = db.query(AiDraft).one()
            assert draft.source_note_id == source_note_id
            assert draft.title == "源笔记标题"
        finally:
            db.close()
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_drafts_api_rejects_cross_user_source_note(tmp_path):
    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "draft-source-owner")
    intruder_token = _register_and_get_access_token("draft-source-intruder")
    try:
        save_response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "account_id": owner_account_id,
                "notes": [{"note_id": "foreign-source", "title": " чужая", "content": "nope"}],
            },
        )
        source_note_id = save_response.json()["items"][0]["id"]

        response = client.post(
            "/api/drafts",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"platform": "xhs", "source_note_id": source_note_id, "intent": "publish"},
        )

        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_drafts_update_persists_owned_changes_and_rejects_cross_user(tmp_path):
    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "draft-update-owner")
    intruder_token = _register_and_get_access_token("draft-update-intruder")
    try:
        save_response = client.post(
            "/api/notes/batch-save",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "account_id": owner_account_id,
                "notes": [{"note_id": "update-source", "title": "旧标题", "content": "旧正文"}],
            },
        )
        source_note_id = save_response.json()["items"][0]["id"]
        create_response = client.post(
            "/api/drafts",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform": "xhs", "source_note_id": source_note_id},
        )
        draft_id = create_response.json()["id"]

        update_response = client.patch(
            f"/api/drafts/{draft_id}",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"title": "新标题", "body": "新正文"},
        )
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["title"] == "新标题"
        assert updated["body"] == "新正文"

        list_response = client.get(
            "/api/drafts?platform=xhs",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        listed = list_response.json()["items"][0]
        assert listed["id"] == draft_id
        assert listed["title"] == "新标题"
        assert listed["body"] == "新正文"

        intruder_response = client.patch(
            f"/api/drafts/{draft_id}",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"title": "攻击标题", "body": "攻击正文"},
        )
        assert intruder_response.status_code == 404
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_model_configs_require_authentication(tmp_path):
    db_dependency = _override_database(tmp_path)
    try:
        response = client.get("/api/model-configs")

        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_model_configs_create_list_filter_and_encrypt_api_key(tmp_path):
    from backend.app.core.database import get_db
    from backend.app.core.security import decrypt_text
    from backend.app.models import ModelConfig

    db_dependency = _override_database(tmp_path)
    owner_token = _register_and_get_access_token("model-owner")
    intruder_token = _register_and_get_access_token("model-intruder")
    try:
        create_response = client.post(
            "/api/model-configs",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "name": "OpenAI Text",
                "model_type": "text",
                "provider": "openai-compatible",
                "model_name": "gpt-test",
                "base_url": "https://api.example.test/v1",
                "api_key": "sk-secret-text",
                "is_default": True,
            },
        )
        assert create_response.status_code == 200
        created = create_response.json()
        assert created["name"] == "OpenAI Text"
        assert created["model_type"] == "text"
        assert created["model_name"] == "gpt-test"
        assert created["has_api_key"] is True
        assert "api_key" not in created
        assert "encrypted_api_key" not in created

        image_response = client.post(
            "/api/model-configs",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "name": "Image Model",
                "model_type": "image",
                "provider": "openai-compatible",
                "model_name": "image-test",
                "base_url": "",
                "api_key": "",
                "is_default": False,
            },
        )
        assert image_response.status_code == 200

        owner_list_response = client.get(
            "/api/model-configs?model_type=text",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert owner_list_response.status_code == 200
        owner_payload = owner_list_response.json()
        assert owner_payload["total"] == 1
        assert owner_payload["items"][0]["id"] == created["id"]
        assert owner_payload["items"][0]["model_type"] == "text"

        intruder_list_response = client.get(
            "/api/model-configs",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_list_response.status_code == 200
        assert intruder_list_response.json()["total"] == 0

        db = next(app.dependency_overrides[get_db]())
        try:
            config = db.query(ModelConfig).filter(ModelConfig.name == "OpenAI Text").one()
            assert config.encrypted_api_key != "sk-secret-text"
            assert decrypt_text(config.encrypted_api_key) == "sk-secret-text"
        finally:
            db.close()
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_text_model_config_defaults_to_gpt_54_when_model_name_omitted(tmp_path):
    db_dependency = _override_database(tmp_path)
    owner_token = _register_and_get_access_token("model-default-owner")
    try:
        response = client.post(
            "/api/model-configs",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "name": "Default Text",
                "model_type": "text",
                "provider": "openai-compatible",
                "base_url": "https://api.example.test/v1",
                "api_key": "sk-default",
                "is_default": True,
            },
        )

        assert response.status_code == 200
        assert response.json()["model_name"] == "gpt-5.4"
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_model_configs_update_and_set_default_are_owner_scoped(tmp_path):
    db_dependency = _override_database(tmp_path)
    owner_token = _register_and_get_access_token("model-update-owner")
    intruder_token = _register_and_get_access_token("model-update-intruder")
    try:
        first_response = client.post(
            "/api/model-configs",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "name": "Text One",
                "model_type": "text",
                "provider": "provider-a",
                "model_name": "model-a",
                "base_url": "https://a.example.test",
                "api_key": "secret-a",
                "is_default": True,
            },
        )
        second_response = client.post(
            "/api/model-configs",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "name": "Text Two",
                "model_type": "text",
                "provider": "provider-b",
                "model_name": "model-b",
                "base_url": "https://b.example.test",
                "api_key": "secret-b",
                "is_default": False,
            },
        )
        first_id = first_response.json()["id"]
        second_id = second_response.json()["id"]

        update_response = client.patch(
            f"/api/model-configs/{second_id}",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"name": "Text Two Updated", "api_key": "secret-b2"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "Text Two Updated"
        assert update_response.json()["has_api_key"] is True

        intruder_update_response = client.patch(
            f"/api/model-configs/{second_id}",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"name": "stolen"},
        )
        assert intruder_update_response.status_code == 404

        default_response = client.post(
            f"/api/model-configs/{second_id}/set-default",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert default_response.status_code == 200
        assert default_response.json()["is_default"] is True

        list_response = client.get(
            "/api/model-configs?model_type=text",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        listed = {item["id"]: item for item in list_response.json()["items"]}
        assert listed[first_id]["is_default"] is False
        assert listed[second_id]["is_default"] is True

        intruder_default_response = client.post(
            f"/api/model-configs/{second_id}/set-default",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_default_response.status_code == 404
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_ai_rewrite_note_requires_authentication(tmp_path):
    db_dependency = _override_database(tmp_path)
    try:
        response = client.post("/api/ai/rewrite-note", json={"draft_id": 1})

        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_ai_rewrite_note_requires_owned_draft_and_default_text_model(tmp_path):
    db_dependency = _override_database(tmp_path)
    owner_token = _register_and_get_access_token("ai-rewrite-owner")
    intruder_token = _register_and_get_access_token("ai-rewrite-intruder")
    try:
        create_response = client.post(
            "/api/drafts",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform": "xhs", "title": "Original title", "body": "Original body"},
        )
        draft_id = create_response.json()["id"]

        no_model_response = client.post(
            "/api/ai/rewrite-note",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"draft_id": draft_id},
        )
        assert no_model_response.status_code == 400
        assert "Default text model" in no_model_response.json()["detail"]

        intruder_response = client.post(
            "/api/ai/rewrite-note",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"draft_id": draft_id},
        )
        assert intruder_response.status_code == 404
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_ai_rewrite_note_uses_default_text_model_and_updates_owned_draft(tmp_path):
    from backend.app.api.ai import get_text_ai_client

    class FakeTextAiClient:
        def __init__(self):
            self.calls = []

        def rewrite_note(self, *, model_config, api_key, title, body, instruction):
            self.calls.append(
                {
                    "model_name": model_config.model_name,
                    "api_key": api_key,
                    "title": title,
                    "body": body,
                    "instruction": instruction,
                }
            )
            return f"改写结果：{title} / {instruction}"

    fake_client = FakeTextAiClient()
    db_dependency = _override_database(tmp_path)
    owner_token = _register_and_get_access_token("ai-rewrite-success")
    try:
        app.dependency_overrides[get_text_ai_client] = lambda: fake_client

        model_response = client.post(
            "/api/model-configs",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "name": "Default Text",
                "model_type": "text",
                "provider": "openai-compatible",
                "model_name": "gpt-rewrite-test",
                "base_url": "https://api.example.test/v1",
                "api_key": "sk-rewrite-secret",
                "is_default": True,
            },
        )
        assert model_response.status_code == 200

        draft_response = client.post(
            "/api/drafts",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform": "xhs", "title": "爆款标题", "body": "原始正文"},
        )
        draft_id = draft_response.json()["id"]

        rewrite_response = client.post(
            "/api/ai/rewrite-note",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"draft_id": draft_id, "instruction": "更适合小红书种草"},
        )
        assert rewrite_response.status_code == 200
        rewritten = rewrite_response.json()
        assert rewritten["id"] == draft_id
        assert rewritten["body"] == "改写结果：爆款标题 / 更适合小红书种草"
        assert fake_client.calls == [
            {
                "model_name": "gpt-rewrite-test",
                "api_key": "sk-rewrite-secret",
                "title": "爆款标题",
                "body": "原始正文",
                "instruction": "更适合小红书种草",
            }
        ]

        list_response = client.get(
            "/api/drafts?platform=xhs",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert list_response.json()["items"][0]["body"] == "改写结果：爆款标题 / 更适合小红书种草"

        tasks_response = client.get(
            "/api/tasks?platform=xhs",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert tasks_response.status_code == 200
        task_payload = tasks_response.json()
        assert task_payload["total"] == 1
        task = task_payload["items"][0]
        assert task["task_type"] == "ai_rewrite"
        assert task["status"] == "completed"
        assert task["progress"] == 100
        assert task["payload"]["draft_id"] == draft_id
        assert task["payload"]["model_config_id"] == model_response.json()["id"]
    finally:
        app.dependency_overrides.pop(get_text_ai_client, None)
        app.dependency_overrides.pop(db_dependency, None)


def test_ai_text_generation_requires_authentication(tmp_path):
    db_dependency = _override_database(tmp_path)
    try:
        response = client.post("/api/ai/generate-note", json={"topic": "低卡早餐"})

        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_ai_text_generation_endpoints_use_default_model_and_create_tasks(tmp_path):
    from backend.app.api.ai import get_text_ai_client

    class FakeTextGenerationClient:
        def __init__(self):
            self.calls = []

        def rewrite_note(self, *, model_config, api_key, title, body, instruction):
            raise AssertionError("rewrite_note should not be called")

        def generate_note(self, *, model_config, api_key, topic, reference, instruction):
            self.calls.append(("generate_note", model_config.model_name, api_key, topic, reference, instruction))
            return {"title": f"{topic} 标题", "body": f"{topic} 正文 {reference} {instruction}".strip()}

        def generate_titles(self, *, model_config, api_key, title, body, count):
            self.calls.append(("generate_titles", model_config.model_name, api_key, title, body, count))
            return ["标题 A", "标题 B"][:count]

        def generate_tags(self, *, model_config, api_key, title, body, count):
            self.calls.append(("generate_tags", model_config.model_name, api_key, title, body, count))
            return ["低卡", "早餐", "通勤"][:count]

        def polish_text(self, *, model_config, api_key, text, instruction):
            self.calls.append(("polish_text", model_config.model_name, api_key, text, instruction))
            return f"润色：{text} / {instruction}"

    fake_client = FakeTextGenerationClient()
    db_dependency = _override_database(tmp_path)
    owner_token = _register_and_get_access_token("ai-generate-owner")
    try:
        app.dependency_overrides[get_text_ai_client] = lambda: fake_client
        model_response = client.post(
            "/api/model-configs",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "name": "Default Text",
                "model_type": "text",
                "provider": "openai-compatible",
                "model_name": "gpt-generate-test",
                "base_url": "https://api.example.test/v1",
                "api_key": "sk-generate-secret",
                "is_default": True,
            },
        )
        assert model_response.status_code == 200

        generate_response = client.post(
            "/api/ai/generate-note",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform": "xhs", "topic": "低卡早餐", "reference": "参考笔记", "instruction": "更具体"},
        )
        assert generate_response.status_code == 200
        generated = generate_response.json()
        assert generated["title"] == "低卡早餐 标题"
        assert generated["body"] == "低卡早餐 正文 参考笔记 更具体"

        titles_response = client.post(
            "/api/ai/generate-title",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"title": "旧标题", "body": "正文", "count": 2},
        )
        assert titles_response.status_code == 200
        assert titles_response.json()["items"] == ["标题 A", "标题 B"]

        tags_response = client.post(
            "/api/ai/generate-tags",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"title": "早餐", "body": "低卡早餐正文", "count": 3},
        )
        assert tags_response.status_code == 200
        assert tags_response.json()["items"] == ["低卡", "早餐", "通勤"]

        polish_response = client.post(
            "/api/ai/polish-text",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"text": "原文", "instruction": "更自然"},
        )
        assert polish_response.status_code == 200
        assert polish_response.json()["text"] == "润色：原文 / 更自然"

        tasks_response = client.get("/api/tasks?platform=xhs", headers={"Authorization": f"Bearer {owner_token}"})
        assert tasks_response.status_code == 200
        task_types = [item["task_type"] for item in tasks_response.json()["items"]]
        assert task_types == ["ai_polish_text", "ai_generate_tags", "ai_generate_title", "ai_generate_note"]
        assert fake_client.calls[0] == (
            "generate_note",
            "gpt-generate-test",
            "sk-generate-secret",
            "低卡早餐",
            "参考笔记",
            "更具体",
        )
    finally:
        app.dependency_overrides.pop(get_text_ai_client, None)
        app.dependency_overrides.pop(db_dependency, None)


def test_ai_image_routes_require_authentication(tmp_path):
    db_dependency = _override_database(tmp_path)
    try:
        response = client.post("/api/ai/images/generate-cover", json={"prompt": "低卡早餐封面"})

        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_ai_image_routes_use_default_model_store_assets_and_enforce_scope(tmp_path):
    from backend.app.api.ai import get_image_ai_client

    class FakeImageAiClient:
        def __init__(self):
            self.calls = []

        def generate_cover(self, *, model_config, api_key, prompt, size, style):
            self.calls.append(("generate_cover", model_config.model_name, api_key, prompt, size, style))
            return {"url": "https://cdn.example.test/cover.png", "raw": {"seed": 1}}

        def describe_image(self, *, model_config, api_key, image_url, instruction):
            self.calls.append(("describe_image", model_config.model_name, api_key, image_url, instruction))
            return "这是一张低卡早餐封面"

    fake_client = FakeImageAiClient()
    db_dependency = _override_database(tmp_path)
    owner_token = _register_and_get_access_token("ai-image-owner")
    intruder_token = _register_and_get_access_token("ai-image-intruder")
    try:
        app.dependency_overrides[get_image_ai_client] = lambda: fake_client
        model_response = client.post(
            "/api/model-configs",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "name": "Default Image",
                "model_type": "image",
                "provider": "openai-compatible",
                "model_name": "image-generate-test",
                "base_url": "https://api.example.test/v1",
                "api_key": "sk-image-secret",
                "is_default": True,
            },
        )
        assert model_response.status_code == 200

        generate_response = client.post(
            "/api/ai/images/generate-cover",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"prompt": "低卡早餐封面", "size": "1024x1024", "style": "clean"},
        )
        assert generate_response.status_code == 200
        generated = generate_response.json()
        assert generated["file_path"] == "https://cdn.example.test/cover.png"
        assert generated["prompt"] == "低卡早餐封面"
        assert generated["model_name"] == "image-generate-test"

        list_response = client.get("/api/ai/images/assets", headers={"Authorization": f"Bearer {owner_token}"})
        assert list_response.status_code == 200
        assert list_response.json()["total"] == 1
        assert list_response.json()["items"][0]["id"] == generated["id"]

        intruder_list_response = client.get("/api/ai/images/assets", headers={"Authorization": f"Bearer {intruder_token}"})
        assert intruder_list_response.status_code == 200
        assert intruder_list_response.json()["total"] == 0

        describe_response = client.post(
            "/api/ai/images/describe",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"image_url": generated["file_path"], "instruction": "描述卖点"},
        )
        assert describe_response.status_code == 200
        assert describe_response.json()["text"] == "这是一张低卡早餐封面"

        tasks_response = client.get("/api/tasks?platform=xhs", headers={"Authorization": f"Bearer {owner_token}"})
        assert tasks_response.status_code == 200
        task_types = [item["task_type"] for item in tasks_response.json()["items"]]
        assert task_types == ["ai_image_describe", "ai_image_generate_cover"]
        assert fake_client.calls == [
            ("generate_cover", "image-generate-test", "sk-image-secret", "低卡早餐封面", "1024x1024", "clean"),
            ("describe_image", "image-generate-test", "sk-image-secret", "https://cdn.example.test/cover.png", "描述卖点"),
        ]
    finally:
        app.dependency_overrides.pop(get_image_ai_client, None)
        app.dependency_overrides.pop(db_dependency, None)


def test_tasks_api_requires_authentication(tmp_path):
    db_dependency = _override_database(tmp_path)
    try:
        response = client.get("/api/tasks?platform=xhs")

        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_tasks_api_lists_only_current_user_tasks_and_filters_platform(tmp_path):
    from backend.app.core.database import get_db
    from backend.app.models import Task

    db_dependency = _override_database(tmp_path)
    owner_token = _register_and_get_access_token("task-owner")
    intruder_token = _register_and_get_access_token("task-intruder")
    try:
        db = next(app.dependency_overrides[get_db]())
        try:
            db.add_all(
                [
                    Task(
                        user_id=1,
                        platform="xhs",
                        task_type="ai_rewrite",
                        status="completed",
                        progress=100,
                        payload={"draft_id": 11},
                    ),
                    Task(
                        user_id=1,
                        platform="douyin",
                        task_type="crawl",
                        status="pending",
                        progress=0,
                        payload={"keyword": "demo"},
                    ),
                    Task(
                        user_id=2,
                        platform="xhs",
                        task_type="publish",
                        status="failed",
                        progress=100,
                        payload={"error": "nope"},
                    ),
                ]
            )
            db.commit()
        finally:
            db.close()

        owner_response = client.get(
            "/api/tasks?platform=xhs",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert owner_response.status_code == 200
        owner_payload = owner_response.json()
        assert owner_payload["total"] == 1
        assert owner_payload["items"][0]["platform"] == "xhs"
        assert owner_payload["items"][0]["task_type"] == "ai_rewrite"
        assert owner_payload["items"][0]["payload"] == {"draft_id": 11}

        intruder_response = client.get(
            "/api/tasks?platform=xhs",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_response.status_code == 200
        assert intruder_response.json()["total"] == 1
        assert intruder_response.json()["items"][0]["task_type"] == "publish"
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_scheduler_status_requires_authentication(tmp_path):
    db_dependency = _override_database(tmp_path)
    try:
        response = client.get("/api/tasks/scheduler/status")

        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_scheduler_status_reports_config_and_recent_owned_scheduler_tasks(tmp_path):
    from backend.app.core.database import get_db
    from backend.app.models import Task

    db_dependency = _override_database(tmp_path)
    owner_token = _register_and_get_access_token("scheduler-status-owner")
    _register_and_get_access_token("scheduler-status-other")
    try:
        db = next(app.dependency_overrides[get_db]())
        try:
            db.add_all(
                [
                    Task(
                        user_id=1,
                        platform="xhs",
                        task_type="monitoring_refresh",
                        status="completed",
                        progress=100,
                        payload={"scheduler": True, "target_id": 1},
                    ),
                    Task(
                        user_id=1,
                        platform="xhs",
                        task_type="ai_rewrite",
                        status="completed",
                        progress=100,
                        payload={"draft_id": 10},
                    ),
                    Task(
                        user_id=1,
                        platform="xhs",
                        task_type="monitoring_refresh",
                        status="pending",
                        progress=0,
                        payload={"target_id": 2},
                    ),
                    Task(
                        user_id=2,
                        platform="xhs",
                        task_type="creator_publish_scheduler",
                        status="completed",
                        progress=100,
                        payload={"publish_job_id": 99},
                    ),
                ]
            )
            db.commit()
        finally:
            db.close()

        response = client.get(
            "/api/tasks/scheduler/status",
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["enabled"] is False
        assert payload["running"] is False
        assert payload["interval_seconds"] == 60
        assert payload["jobs"] == []
        assert [task["task_type"] for task in payload["recent_tasks"]] == ["monitoring_refresh"]
        assert payload["recent_tasks"][0]["payload"] == {"scheduler": True, "target_id": 1}
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_tasks_detail_enforces_ownership(tmp_path):
    from backend.app.core.database import get_db
    from backend.app.models import Task

    db_dependency = _override_database(tmp_path)
    owner_token = _register_and_get_access_token("task-detail-owner")
    intruder_token = _register_and_get_access_token("task-detail-intruder")
    try:
        db = next(app.dependency_overrides[get_db]())
        try:
            task = Task(
                user_id=1,
                platform="xhs",
                task_type="ai_rewrite",
                status="completed",
                progress=100,
                payload={"draft_id": 22},
            )
            db.add(task)
            db.commit()
            task_id = task.id
        finally:
            db.close()

        owner_response = client.get(
            f"/api/tasks/{task_id}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert owner_response.status_code == 200
        assert owner_response.json()["id"] == task_id
        assert owner_response.json()["payload"] == {"draft_id": 22}

        intruder_response = client.get(
            f"/api/tasks/{task_id}",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_response.status_code == 404
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_task_execution_fields_and_retry_with_exhausted_status(tmp_path):
    from backend.app.core.database import get_db
    from backend.app.core.time import shanghai_now
    from backend.app.models import Task

    db_dependency = _override_database(tmp_path)
    token = _register_and_get_access_token("task-fields-user")
    try:
        db = next(app.dependency_overrides[get_db]())
        try:
            now = shanghai_now()
            parent = Task(
                user_id=1, platform="xhs", task_type="monitoring_crawl",
                status="completed", progress=100,
                started_at=now, finished_at=now,
            )
            child = Task(
                user_id=1, platform="xhs", task_type="note_crawl",
                status="failed", progress=0, error_type="network",
                retry_count=2, max_retries=3,
                started_at=now, finished_at=now,
            )
            db.add(parent)
            db.flush()
            child.parent_task_id = parent.id
            db.add(child)
            db.commit()
            parent_id, child_id = parent.id, child.id
        finally:
            db.close()

        detail = client.get(f"/api/tasks/{parent_id}", headers={"Authorization": f"Bearer {token}"})
        assert detail.status_code == 200
        body = detail.json()
        assert body["started_at"] is not None
        assert body["finished_at"] is not None
        assert body["duration_ms"] is not None
        assert body["duration_ms"] >= 0
        assert len(body["children"]) == 1
        assert body["children"][0]["id"] == child_id
        assert body["children"][0]["error_type"] == "network"

        child_detail = client.get(f"/api/tasks/{child_id}", headers={"Authorization": f"Bearer {token}"})
        assert child_detail.json()["parent_task_id"] == parent_id
        assert child_detail.json()["retry_count"] == 2
        assert child_detail.json()["max_retries"] == 3

        retry = client.post(f"/api/tasks/{child_id}/retry", headers={"Authorization": f"Bearer {token}"})
        assert retry.status_code == 200
        assert retry.json()["status"] == "pending"
        assert retry.json()["retry_count"] == 3
        assert retry.json()["error_type"] is None

        db2 = next(app.dependency_overrides[get_db]())
        try:
            t = db2.get(Task, child_id)
            t.status = "exhausted"
            t.error_type = "network"
            db2.commit()
        finally:
            db2.close()

        exhausted_retry = client.post(f"/api/tasks/{child_id}/retry", headers={"Authorization": f"Bearer {token}"})
        assert exhausted_retry.status_code == 200
        assert exhausted_retry.json()["status"] == "pending"
    finally:
        app.dependency_overrides.pop(db_dependency, None)
    db_dependency = _override_database(tmp_path)
    try:
        response = client.post("/api/drafts/1/send-to-publish", json={"platform_account_id": 1})

        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_notifications_crud_and_trigger_helpers(tmp_path):
    from backend.app.core.database import get_db
    from backend.app.models import Notification, Task
    from backend.app.services.notification_service import notify_task_failed, notify_task_exhausted

    db_dependency = _override_database(tmp_path)
    token = _register_and_get_access_token("notif-user")
    other_token = _register_and_get_access_token("notif-other")
    try:
        db = next(app.dependency_overrides[get_db]())
        try:
            task = Task(user_id=1, platform="xhs", task_type="ai_rewrite", status="failed", error_type="network")
            db.add(task)
            db.flush()
            n1 = notify_task_failed(db, task)
            task.status = "exhausted"
            n2 = notify_task_exhausted(db, task)
            other_n = Notification(user_id=2, title="other", level="info")
            db.add(other_n)
            db.commit()
        finally:
            db.close()

        unauth = client.get("/api/notifications")
        assert unauth.status_code == 401

        listing = client.get("/api/notifications", headers={"Authorization": f"Bearer {token}"})
        assert listing.status_code == 200
        items = listing.json()["items"]
        assert len(items) == 2
        levels = {items[0]["level"], items[1]["level"]}
        assert levels == {"warning", "error"}

        unread_only = client.get("/api/notifications?unread=true", headers={"Authorization": f"Bearer {token}"})
        assert len(unread_only.json()["items"]) == 2

        mark = client.post(f"/api/notifications/{items[0]['id']}/read", headers={"Authorization": f"Bearer {token}"})
        assert mark.status_code == 200
        assert mark.json()["read"] is True

        unread_after = client.get("/api/notifications?unread=true", headers={"Authorization": f"Bearer {token}"})
        assert len(unread_after.json()["items"]) == 1

        mark_all = client.post("/api/notifications/read-all", headers={"Authorization": f"Bearer {token}"})
        assert mark_all.status_code == 200
        assert mark_all.json()["marked"] == 1

        other_listing = client.get("/api/notifications", headers={"Authorization": f"Bearer {other_token}"})
        assert len(other_listing.json()["items"]) == 1

        cross_mark = client.post(f"/api/notifications/{items[0]['id']}/read", headers={"Authorization": f"Bearer {other_token}"})
        assert cross_mark.status_code == 404
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_draft_send_to_publish_creates_job_and_enforces_ownership(tmp_path):
    from backend.app.core.database import get_db
    from backend.app.models import PublishJob

    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "publish-owner")
    intruder_token = _register_and_get_access_token("publish-intruder")
    try:
        draft_response = client.post(
            "/api/drafts",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform": "xhs", "title": "Ready title", "body": "Ready body"},
        )
        draft_id = draft_response.json()["id"]

        create_response = client.post(
            f"/api/drafts/{draft_id}/send-to-publish",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform_account_id": owner_account_id, "publish_mode": "immediate"},
        )
        assert create_response.status_code == 200
        created = create_response.json()
        assert created["platform"] == "xhs"
        assert created["platform_account_id"] == owner_account_id
        assert created["source_draft_id"] == draft_id
        assert created["title"] == "Ready title"
        assert created["body"] == "Ready body"
        assert created["publish_mode"] == "immediate"
        assert created["status"] == "pending"

        intruder_draft_response = client.post(
            f"/api/drafts/{draft_id}/send-to-publish",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"platform_account_id": owner_account_id, "publish_mode": "immediate"},
        )
        assert intruder_draft_response.status_code == 404

        db = next(app.dependency_overrides[get_db]())
        try:
            publish_job = db.query(PublishJob).one()
            assert publish_job.source_draft_id == draft_id
            assert publish_job.platform_account_id == owner_account_id
        finally:
            db.close()
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_publish_jobs_list_requires_auth_and_filters_current_user(tmp_path):
    from backend.app.core.database import get_db
    from backend.app.core.security import encrypt_text
    from backend.app.models import AccountCookieVersion, PlatformAccount

    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "publish-list-owner")
    intruder_token = _register_and_get_access_token("publish-list-intruder")
    try:
        db = next(app.dependency_overrides[get_db]())
        try:
            intruder_account = PlatformAccount(
                user_id=2,
                platform="xhs",
                sub_type="pc",
                external_user_id="publish-list-intruder",
                nickname="发布测试账号",
                status="active",
            )
            db.add(intruder_account)
            db.flush()
            db.add(
                AccountCookieVersion(
                    platform_account_id=intruder_account.id,
                    encrypted_cookies=encrypt_text('{"a1":"intruder-a1"}'),
                )
            )
            db.commit()
            intruder_account_id = intruder_account.id
        finally:
            db.close()

        owner_draft_response = client.post(
            "/api/drafts",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform": "xhs", "title": "Owner publish", "body": "Owner body"},
        )
        owner_draft_id = owner_draft_response.json()["id"]
        owner_create_response = client.post(
            f"/api/drafts/{owner_draft_id}/send-to-publish",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform_account_id": owner_account_id},
        )
        assert owner_create_response.status_code == 200

        intruder_draft_response = client.post(
            "/api/drafts",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"platform": "xhs", "title": "Intruder publish", "body": "Intruder body"},
        )
        intruder_draft_id = intruder_draft_response.json()["id"]
        intruder_create_response = client.post(
            f"/api/drafts/{intruder_draft_id}/send-to-publish",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"platform_account_id": intruder_account_id},
        )
        assert intruder_create_response.status_code == 200

        anonymous_response = client.get("/api/publish/jobs?platform=xhs")
        assert anonymous_response.status_code == 401

        owner_list_response = client.get(
            "/api/publish/jobs?platform=xhs",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert owner_list_response.status_code == 200
        owner_payload = owner_list_response.json()
        assert owner_payload["total"] == 1
        assert owner_payload["items"][0]["title"] == "Owner publish"

        intruder_list_response = client.get(
            "/api/publish/jobs?platform=xhs",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_list_response.status_code == 200
        intruder_payload = intruder_list_response.json()
        assert intruder_payload["total"] == 1
        assert intruder_payload["items"][0]["title"] == "Intruder publish"
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_publish_job_detail_and_update_enforce_ownership(tmp_path):
    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "publish-detail-owner")
    intruder_token = _register_and_get_access_token("publish-detail-intruder")
    try:
        draft_response = client.post(
            "/api/drafts",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform": "xhs", "title": "Draft title", "body": "Draft body"},
        )
        draft_id = draft_response.json()["id"]
        create_response = client.post(
            f"/api/drafts/{draft_id}/send-to-publish",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform_account_id": owner_account_id},
        )
        job_id = create_response.json()["id"]

        owner_detail_response = client.get(
            f"/api/publish/jobs/{job_id}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert owner_detail_response.status_code == 200
        assert owner_detail_response.json()["title"] == "Draft title"

        intruder_detail_response = client.get(
            f"/api/publish/jobs/{job_id}",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_detail_response.status_code == 404

        update_response = client.patch(
            f"/api/publish/jobs/{job_id}",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "title": "Edited publish title",
                "body": "Edited publish body",
                "publish_mode": "scheduled",
                "scheduled_at": "2030-01-02T03:04:05",
            },
        )
        assert update_response.status_code == 200
        updated = update_response.json()
        assert updated["title"] == "Edited publish title"
        assert updated["body"] == "Edited publish body"
        assert updated["publish_mode"] == "scheduled"
        assert updated["scheduled_at"] == "2030-01-02T03:04:05"

        list_response = client.get(
            "/api/publish/jobs?platform=xhs",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert list_response.json()["items"][0]["title"] == "Edited publish title"

        intruder_update_response = client.patch(
            f"/api/publish/jobs/{job_id}",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"title": "stolen"},
        )
        assert intruder_update_response.status_code == 404
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_publish_assets_api_requires_authentication(tmp_path):
    db_dependency = _override_database(tmp_path)
    try:
        response = client.get("/api/publish/jobs/1/assets")

        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_publish_assets_api_adds_lists_and_deletes_owned_assets(tmp_path):
    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(tmp_path, "publish-assets-owner")
    intruder_token = _register_and_get_access_token("publish-assets-intruder")
    try:
        draft_response = client.post(
            "/api/drafts",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform": "xhs", "title": "Asset title", "body": "Asset body"},
        )
        draft_id = draft_response.json()["id"]
        job_response = client.post(
            f"/api/drafts/{draft_id}/send-to-publish",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform_account_id": owner_account_id},
        )
        job_id = job_response.json()["id"]

        create_response = client.post(
            f"/api/publish/jobs/{job_id}/assets",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"asset_type": "image", "file_path": "storage/media/cover.png"},
        )
        assert create_response.status_code == 200
        created = create_response.json()
        assert created["publish_job_id"] == job_id
        assert created["asset_type"] == "image"
        assert created["file_path"] == "storage/media/cover.png"

        list_response = client.get(
            f"/api/publish/jobs/{job_id}/assets",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert list_response.status_code == 200
        assert list_response.json()["total"] == 1
        assert list_response.json()["items"][0]["id"] == created["id"]

        intruder_list_response = client.get(
            f"/api/publish/jobs/{job_id}/assets",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_list_response.status_code == 404

        intruder_delete_response = client.delete(
            f"/api/publish/assets/{created['id']}",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_delete_response.status_code == 404

        delete_response = client.delete(
            f"/api/publish/assets/{created['id']}",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert delete_response.status_code == 200
        assert delete_response.json()["status"] == "deleted"

        empty_response = client.get(
            f"/api/publish/jobs/{job_id}/assets",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert empty_response.json()["total"] == 0
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_publish_asset_upload_requires_authentication(tmp_path):
    db_dependency = _override_database(tmp_path)
    try:
        response = client.post("/api/publish/assets/1/upload")

        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_publish_asset_upload_uses_creator_cookie_and_updates_asset(tmp_path):
    from backend.app.api.publish import get_creator_publish_adapter_factory

    class FakeCreatorPublishAdapter:
        calls = []

        def __init__(self, cookies):
            self.cookies = cookies

        def upload_media(self, file_path, media_type):
            self.calls.append({"cookies": self.cookies, "file_path": file_path, "media_type": media_type})
            return {"creator_media_id": "creator-media-001", "fileIds": "file-001"}

    db_dependency, owner_token, creator_account_id = _create_creator_account_with_cookie(
        tmp_path, "publish-upload-owner"
    )
    FakeCreatorPublishAdapter.calls = []
    app.dependency_overrides[get_creator_publish_adapter_factory] = lambda: FakeCreatorPublishAdapter
    try:
        draft_response = client.post(
            "/api/drafts",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform": "xhs", "title": "Upload title", "body": "Upload body"},
        )
        draft_id = draft_response.json()["id"]
        job_response = client.post(
            f"/api/drafts/{draft_id}/send-to-publish",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform_account_id": creator_account_id},
        )
        job_id = job_response.json()["id"]
        asset_response = client.post(
            f"/api/publish/jobs/{job_id}/assets",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"asset_type": "image", "file_path": "storage/media/cover.png"},
        )
        asset_id = asset_response.json()["id"]

        upload_response = client.post(
            f"/api/publish/assets/{asset_id}/upload",
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        assert upload_response.status_code == 200
        uploaded = upload_response.json()
        assert uploaded["upload_status"] == "uploaded"
        assert uploaded["creator_media_id"] == "creator-media-001"
        assert uploaded["upload_error"] == ""
        assert FakeCreatorPublishAdapter.calls == [
            {
                "cookies": "web_session=creator-session; a1=creator-a1",
                "file_path": "storage/media/cover.png",
                "media_type": "image",
            }
        ]
    finally:
        app.dependency_overrides.pop(get_creator_publish_adapter_factory, None)
        app.dependency_overrides.pop(db_dependency, None)


def test_publish_asset_upload_rejects_cross_user_asset(tmp_path):
    from backend.app.api.publish import get_creator_publish_adapter_factory

    class FakeCreatorPublishAdapter:
        def __init__(self, cookies):
            raise AssertionError("cross-user upload must not instantiate adapter")

    db_dependency, owner_token, creator_account_id = _create_creator_account_with_cookie(
        tmp_path, "publish-upload-cross-owner"
    )
    intruder_token = _register_and_get_access_token("publish-upload-cross-intruder")
    app.dependency_overrides[get_creator_publish_adapter_factory] = lambda: FakeCreatorPublishAdapter
    try:
        draft_response = client.post(
            "/api/drafts",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform": "xhs", "title": "Owner asset", "body": "Owner body"},
        )
        draft_id = draft_response.json()["id"]
        job_response = client.post(
            f"/api/drafts/{draft_id}/send-to-publish",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform_account_id": creator_account_id},
        )
        job_id = job_response.json()["id"]
        asset_response = client.post(
            f"/api/publish/jobs/{job_id}/assets",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"asset_type": "image", "file_path": "storage/media/cover.png"},
        )
        asset_id = asset_response.json()["id"]

        response = client.post(
            f"/api/publish/assets/{asset_id}/upload",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )

        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_creator_publish_adapter_factory, None)
        app.dependency_overrides.pop(db_dependency, None)


def test_publish_job_publish_requires_authentication(tmp_path):
    db_dependency = _override_database(tmp_path)
    try:
        response = client.post("/api/publish/jobs/1/publish")

        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_publish_job_publish_uses_creator_cookie_and_updates_status(tmp_path):
    from backend.app.api.publish import get_creator_publish_adapter_factory
    from backend.app.core.database import get_db
    from backend.app.models import Task

    class FakeCreatorPublishAdapter:
        calls = []

        def __init__(self, cookies):
            self.cookies = cookies

        def post_note(self, note_info):
            self.calls.append({"cookies": self.cookies, "note_info": note_info})
            return {"note_id": "xhs-note-001", "success": True}

        def upload_media(self, file_path, media_type):
            return {"creator_media_id": "creator-media-001", "fileIds": "file-001", "width": 1080, "height": 1440}

    db_dependency, owner_token, creator_account_id = _create_creator_account_with_cookie(
        tmp_path, "publish-action-owner"
    )
    FakeCreatorPublishAdapter.calls = []
    app.dependency_overrides[get_creator_publish_adapter_factory] = lambda: FakeCreatorPublishAdapter
    try:
        draft_response = client.post(
            "/api/drafts",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform": "xhs", "title": "Publish title", "body": "Publish body"},
        )
        draft_id = draft_response.json()["id"]
        job_response = client.post(
            f"/api/drafts/{draft_id}/send-to-publish",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform_account_id": creator_account_id},
        )
        job_id = job_response.json()["id"]
        asset_response = client.post(
            f"/api/publish/jobs/{job_id}/assets",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"asset_type": "image", "file_path": "storage/media/cover.png"},
        )
        asset_id = asset_response.json()["id"]
        upload_response = client.post(
            f"/api/publish/assets/{asset_id}/upload",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert upload_response.status_code == 200

        publish_response = client.post(
            f"/api/publish/jobs/{job_id}/publish",
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        assert publish_response.status_code == 200
        published = publish_response.json()
        assert published["status"] == "published"
        assert published["external_note_id"] == "xhs-note-001"
        assert published["publish_error"] == ""
        assert published["published_at"] is not None
        assert FakeCreatorPublishAdapter.calls == [
            {
                "cookies": "web_session=creator-session; a1=creator-a1",
                "note_info": {
                    "title": "Publish title",
                    "desc": "Publish body",
                    "media_type": "image",
                    "image_file_infos": [
                        {
                            "creator_media_id": "creator-media-001",
                            "fileIds": "file-001",
                            "width": 1080,
                            "height": 1440,
                        }
                    ],
                    "type": 1,
                    "postTime": None,
                },
            }
        ]

        db = next(app.dependency_overrides[get_db]())
        try:
            task = db.query(Task).filter(Task.task_type == "creator_publish").one()
            assert task.user_id == 1
            assert task.platform == "xhs"
            assert task.status == "completed"
            assert task.progress == 100
            assert task.payload["publish_job_id"] == job_id
            assert task.payload["external_note_id"] == "xhs-note-001"
        finally:
            db.close()
    finally:
        app.dependency_overrides.pop(get_creator_publish_adapter_factory, None)
        app.dependency_overrides.pop(db_dependency, None)


def test_publish_job_publish_passes_optional_creator_parameters(tmp_path):
    from backend.app.api.publish import get_creator_publish_adapter_factory

    class FakeCreatorOptionalPublishAdapter:
        calls = []

        def __init__(self, cookies):
            self.cookies = cookies

        def post_note(self, note_info):
            self.calls.append({"cookies": self.cookies, "note_info": note_info})
            return {"note_id": "optional-job-note", "success": True}

        def upload_media(self, file_path, media_type):
            return {"creator_media_id": "creator-media-optional", "fileIds": "file-optional", "width": 1080, "height": 1440}

    db_dependency, owner_token, creator_account_id = _create_creator_account_with_cookie(
        tmp_path, "publish-optional-owner"
    )
    FakeCreatorOptionalPublishAdapter.calls = []
    app.dependency_overrides[get_creator_publish_adapter_factory] = lambda: FakeCreatorOptionalPublishAdapter
    try:
        draft_response = client.post(
            "/api/drafts",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform": "xhs", "title": "Optional title", "body": ""},
        )
        draft_id = draft_response.json()["id"]
        job_response = client.post(
            f"/api/drafts/{draft_id}/send-to-publish",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "platform_account_id": creator_account_id,
                "topics": ["早餐"],
                "location": "上海",
                "is_private": False,
            },
        )
        job_id = job_response.json()["id"]
        assert job_response.json()["publish_options"] == {
            "topics": ["早餐"],
            "location": "上海",
            "is_private": False,
            "privacy_type": 0,
        }

        asset_response = client.post(
            f"/api/publish/jobs/{job_id}/assets",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"asset_type": "image", "file_path": "storage/media/cover.png"},
        )
        asset_id = asset_response.json()["id"]
        upload_response = client.post(
            f"/api/publish/assets/{asset_id}/upload",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert upload_response.status_code == 200

        update_response = client.patch(
            f"/api/publish/jobs/{job_id}",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"topics": ["早餐", "通勤"], "is_private": True, "location": ""},
        )
        assert update_response.status_code == 200
        assert update_response.json()["publish_options"] == {
            "topics": ["早餐", "通勤"],
            "is_private": True,
            "privacy_type": 1,
        }

        publish_response = client.post(
            f"/api/publish/jobs/{job_id}/publish",
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        assert publish_response.status_code == 200
        assert FakeCreatorOptionalPublishAdapter.calls == [
            {
                "cookies": "web_session=creator-session; a1=creator-a1",
                "note_info": {
                    "title": "Optional title",
                    "desc": "",
                    "media_type": "image",
                    "image_file_infos": [
                        {
                            "creator_media_id": "creator-media-optional",
                            "fileIds": "file-optional",
                            "width": 1080,
                            "height": 1440,
                        }
                    ],
                    "type": 1,
                    "postTime": None,
                    "topics": ["早餐", "通勤"],
                },
            }
        ]
    finally:
        app.dependency_overrides.pop(get_creator_publish_adapter_factory, None)
        app.dependency_overrides.pop(db_dependency, None)


def test_publish_job_publish_records_failed_task(tmp_path):
    from backend.app.api.publish import get_creator_publish_adapter_factory
    from backend.app.core.database import get_db
    from backend.app.models import Task

    class FakeFailingCreatorPublishAdapter:
        def __init__(self, cookies):
            self.cookies = cookies

        def post_note(self, note_info):
            raise RuntimeError("creator publish denied")

        def upload_media(self, file_path, media_type):
            return {"creator_media_id": "creator-media-001", "fileIds": "file-001", "width": 1080, "height": 1440}

    db_dependency, owner_token, creator_account_id = _create_creator_account_with_cookie(
        tmp_path, "publish-action-failed-owner"
    )
    app.dependency_overrides[get_creator_publish_adapter_factory] = lambda: FakeFailingCreatorPublishAdapter
    try:
        draft_response = client.post(
            "/api/drafts",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform": "xhs", "title": "Publish title", "body": "Publish body"},
        )
        draft_id = draft_response.json()["id"]
        job_response = client.post(
            f"/api/drafts/{draft_id}/send-to-publish",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform_account_id": creator_account_id},
        )
        job_id = job_response.json()["id"]
        asset_response = client.post(
            f"/api/publish/jobs/{job_id}/assets",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"asset_type": "image", "file_path": "storage/media/cover.png"},
        )
        asset_id = asset_response.json()["id"]
        upload_response = client.post(
            f"/api/publish/assets/{asset_id}/upload",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert upload_response.status_code == 200

        publish_response = client.post(
            f"/api/publish/jobs/{job_id}/publish",
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        assert publish_response.status_code == 502
        db = next(app.dependency_overrides[get_db]())
        try:
            task = db.query(Task).filter(Task.task_type == "creator_publish").one()
            assert task.status == "failed"
            assert task.progress == 100
            assert task.payload["publish_job_id"] == job_id
            assert task.payload["error"] == "creator publish denied"
        finally:
            db.close()
    finally:
        app.dependency_overrides.pop(get_creator_publish_adapter_factory, None)
        app.dependency_overrides.pop(db_dependency, None)


def test_publish_job_publish_rejects_empty_content_before_adapter(tmp_path):
    from backend.app.api.publish import get_creator_publish_adapter_factory
    from backend.app.core.database import get_db
    from backend.app.models import Task

    class FakeCreatorPublishAdapter:
        def __init__(self, cookies):
            raise AssertionError("invalid publish content must not instantiate adapter")

    db_dependency, owner_token, creator_account_id = _create_creator_account_with_cookie(
        tmp_path, "publish-preflight-owner"
    )
    app.dependency_overrides[get_creator_publish_adapter_factory] = lambda: FakeCreatorPublishAdapter
    try:
        draft_response = client.post(
            "/api/drafts",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform": "xhs", "title": "Valid title", "body": "Valid body"},
        )
        draft_id = draft_response.json()["id"]
        job_response = client.post(
            f"/api/drafts/{draft_id}/send-to-publish",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform_account_id": creator_account_id},
        )
        job_id = job_response.json()["id"]

        update_response = client.patch(
            f"/api/publish/jobs/{job_id}",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"title": "   ", "body": ""},
        )
        assert update_response.status_code == 200

        publish_response = client.post(
            f"/api/publish/jobs/{job_id}/publish",
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        assert publish_response.status_code == 400
        assert publish_response.json()["detail"] == "Publish title is required"
        db = next(app.dependency_overrides[get_db]())
        try:
            assert db.query(Task).filter(Task.task_type == "creator_publish").count() == 0
        finally:
            db.close()
    finally:
        app.dependency_overrides.pop(get_creator_publish_adapter_factory, None)
        app.dependency_overrides.pop(db_dependency, None)


def test_publish_job_publish_rejects_past_scheduled_time_before_adapter(tmp_path):
    from backend.app.api.publish import get_creator_publish_adapter_factory
    from backend.app.core.database import get_db
    from backend.app.core.time import shanghai_now
    from backend.app.models import PublishAsset, Task

    class FakeCreatorPublishAdapter:
        def __init__(self, cookies):
            raise AssertionError("past scheduled publish must not instantiate adapter")

    db_dependency, owner_token, creator_account_id = _create_creator_account_with_cookie(
        tmp_path, "publish-past-schedule-owner"
    )
    app.dependency_overrides[get_creator_publish_adapter_factory] = lambda: FakeCreatorPublishAdapter
    try:
        draft_response = client.post(
            "/api/drafts",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform": "xhs", "title": "Scheduled title", "body": "Scheduled body"},
        )
        draft_id = draft_response.json()["id"]
        job_response = client.post(
            f"/api/drafts/{draft_id}/send-to-publish",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform_account_id": creator_account_id},
        )
        job_id = job_response.json()["id"]

        update_response = client.patch(
            f"/api/publish/jobs/{job_id}",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "publish_mode": "scheduled",
                "scheduled_at": (shanghai_now() - timedelta(minutes=5)).isoformat(),
            },
        )
        assert update_response.status_code == 200

        db = next(app.dependency_overrides[get_db]())
        try:
            db.add(
                PublishAsset(
                    publish_job_id=job_id,
                    asset_type="image",
                    file_path="storage/media/cover.png",
                    upload_status="uploaded",
                    creator_media_id="creator-media-001",
                    creator_upload_info='{"fileIds":"file-001","width":1080,"height":1440}',
                )
            )
            db.commit()
        finally:
            db.close()

        publish_response = client.post(
            f"/api/publish/jobs/{job_id}/publish",
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        assert publish_response.status_code == 400
        assert publish_response.json()["detail"] == "Scheduled publish time must be in the future"
        db = next(app.dependency_overrides[get_db]())
        try:
            assert db.query(Task).filter(Task.task_type == "creator_publish").count() == 0
        finally:
            db.close()
    finally:
        app.dependency_overrides.pop(get_creator_publish_adapter_factory, None)
        app.dependency_overrides.pop(db_dependency, None)


def test_publish_job_publish_rejects_already_completed_job(tmp_path):
    from backend.app.api.publish import get_creator_publish_adapter_factory
    from backend.app.core.database import get_db
    from backend.app.models import Task

    class FakeCreatorPublishAdapter:
        calls = []

        def __init__(self, cookies):
            self.cookies = cookies

        def post_note(self, note_info):
            self.calls.append({"cookies": self.cookies, "note_info": note_info})
            return {"note_id": "xhs-note-001", "success": True}

        def upload_media(self, file_path, media_type):
            return {"creator_media_id": "creator-media-001", "fileIds": "file-001", "width": 1080, "height": 1440}

    db_dependency, owner_token, creator_account_id = _create_creator_account_with_cookie(
        tmp_path, "publish-completed-owner"
    )
    FakeCreatorPublishAdapter.calls = []
    app.dependency_overrides[get_creator_publish_adapter_factory] = lambda: FakeCreatorPublishAdapter
    try:
        draft_response = client.post(
            "/api/drafts",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform": "xhs", "title": "Publish title", "body": "Publish body"},
        )
        draft_id = draft_response.json()["id"]
        job_response = client.post(
            f"/api/drafts/{draft_id}/send-to-publish",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform_account_id": creator_account_id},
        )
        job_id = job_response.json()["id"]
        asset_response = client.post(
            f"/api/publish/jobs/{job_id}/assets",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"asset_type": "image", "file_path": "storage/media/cover.png"},
        )
        asset_id = asset_response.json()["id"]
        upload_response = client.post(
            f"/api/publish/assets/{asset_id}/upload",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert upload_response.status_code == 200

        first_response = client.post(
            f"/api/publish/jobs/{job_id}/publish",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert first_response.status_code == 200

        second_response = client.post(
            f"/api/publish/jobs/{job_id}/publish",
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        assert second_response.status_code == 400
        assert second_response.json()["detail"] == "Publish job is already completed"
        assert len(FakeCreatorPublishAdapter.calls) == 1
        db = next(app.dependency_overrides[get_db]())
        try:
            assert db.query(Task).filter(Task.task_type == "creator_publish").count() == 1
        finally:
            db.close()
    finally:
        app.dependency_overrides.pop(get_creator_publish_adapter_factory, None)
        app.dependency_overrides.pop(db_dependency, None)


def test_publish_job_publish_rejects_cross_user_job(tmp_path):
    from backend.app.api.publish import get_creator_publish_adapter_factory

    class FakeCreatorPublishAdapter:
        def __init__(self, cookies):
            raise AssertionError("cross-user publish must not instantiate adapter")

    db_dependency, owner_token, creator_account_id = _create_creator_account_with_cookie(
        tmp_path, "publish-action-cross-owner"
    )
    intruder_token = _register_and_get_access_token("publish-action-cross-intruder")
    app.dependency_overrides[get_creator_publish_adapter_factory] = lambda: FakeCreatorPublishAdapter
    try:
        draft_response = client.post(
            "/api/drafts",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform": "xhs", "title": "Owner publish", "body": "Owner body"},
        )
        draft_id = draft_response.json()["id"]
        job_response = client.post(
            f"/api/drafts/{draft_id}/send-to-publish",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={"platform_account_id": creator_account_id},
        )
        job_id = job_response.json()["id"]

        response = client.post(
            f"/api/publish/jobs/{job_id}/publish",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )

        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_creator_publish_adapter_factory, None)
        app.dependency_overrides.pop(db_dependency, None)


def test_image_utility_routes_require_authentication(tmp_path):
    db_dependency = _override_database(tmp_path)
    try:
        compose_response = client.post(
            "/api/files/images/compose",
            json={"title": "低卡早餐", "body": "三分钟做完", "width": 720, "height": 960},
        )
        resize_response = client.post(
            "/api/files/images/resize",
            json={"source_file_name": "xhs-image-u1-missing.png", "width": 320, "height": 320},
        )
        download_response = client.get("/api/files/media/xhs-image-u1-missing.png")

        assert compose_response.status_code == 401
        assert resize_response.status_code == 401
        assert download_response.status_code == 404
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_image_utilities_compose_resize_download_and_enforce_scope(tmp_path):
    db_dependency = _override_database(tmp_path)
    try:
        owner_token = _register_and_get_access_token("image-utility-owner")
        intruder_token = _register_and_get_access_token("image-utility-intruder")

        compose_response = client.post(
            "/api/files/images/compose",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "title": "低卡早餐合集",
                "body": "适合通勤前快速准备的小红书封面",
                "width": 720,
                "height": 960,
                "accent_color": "#111111",
            },
        )

        assert compose_response.status_code == 200
        composed = compose_response.json()
        assert composed["file_name"].startswith("xhs-image-u1-")
        assert composed["file_name"].endswith(".png")
        assert composed["download_url"] == f"/api/files/media/{composed['file_name']}"
        assert composed["width"] == 720
        assert composed["height"] == 960
        assert composed["media_type"] == "image/png"

        download_response = client.get(
            composed["download_url"],
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert download_response.status_code == 200
        assert download_response.headers["content-type"].startswith("image/png")
        assert download_response.content.startswith(b"\x89PNG")

        resize_response = client.post(
            "/api/files/images/resize",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "source_file_name": composed["file_name"],
                "width": 320,
                "height": 320,
                "mode": "cover",
                "format": "jpeg",
                "quality": 82,
            },
        )

        assert resize_response.status_code == 200
        resized = resize_response.json()
        assert resized["file_name"].startswith("xhs-image-u1-")
        assert resized["file_name"].endswith(".jpg")
        assert resized["file_name"] != composed["file_name"]
        assert resized["width"] == 320
        assert resized["height"] == 320
        assert resized["media_type"] == "image/jpeg"

        resized_download_response = client.get(
            resized["download_url"],
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        assert resized_download_response.status_code == 200
        assert resized_download_response.content.startswith(b"\xff\xd8")

        forbidden_download = client.get(
            composed["download_url"],
        )
        assert forbidden_download.status_code == 200

        forbidden_resize = client.post(
            "/api/files/images/resize",
            headers={"Authorization": f"Bearer {intruder_token}"},
            json={"source_file_name": composed["file_name"], "width": 320, "height": 320},
        )
        assert forbidden_resize.status_code == 404
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_publish_job_retry_and_cancel_require_authentication(tmp_path):
    db_dependency = _override_database(tmp_path)
    try:
        retry_response = client.post("/api/publish/jobs/1/retry")
        cancel_response = client.post("/api/publish/jobs/1/cancel")

        assert retry_response.status_code == 401
        assert cancel_response.status_code == 401
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_publish_job_retry_resets_failed_job_and_enforces_ownership(tmp_path):
    from backend.app.core.database import get_db
    from backend.app.models import PublishJob, Task

    db_dependency, owner_token, creator_account_id = _create_creator_account_with_cookie(
        tmp_path, "publish-retry-owner"
    )
    intruder_token = _register_and_get_access_token("publish-retry-intruder")
    db = next(app.dependency_overrides[get_db]())
    try:
        failed_job = PublishJob(
            user_id=1,
            platform_account_id=creator_account_id,
            platform="xhs",
            title="Failed title",
            body="Failed body",
            status="failed",
            external_note_id="old-note",
            publish_error="creator denied",
            published_at=datetime.utcnow(),
        )
        db.add(failed_job)
        db.commit()
        db.refresh(failed_job)
        job_id = failed_job.id
    finally:
        db.close()

    try:
        forbidden_response = client.post(
            f"/api/publish/jobs/{job_id}/retry",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert forbidden_response.status_code == 404

        retry_response = client.post(
            f"/api/publish/jobs/{job_id}/retry",
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        assert retry_response.status_code == 200
        retried = retry_response.json()
        assert retried["status"] == "pending"
        assert retried["publish_error"] == ""
        assert retried["external_note_id"] == ""
        assert retried["published_at"] is None

        db = next(app.dependency_overrides[get_db]())
        try:
            task = db.query(Task).filter(Task.task_type == "creator_publish_retry").one()
            assert task.user_id == 1
            assert task.status == "pending"
            assert task.progress == 0
            assert task.payload["publish_job_id"] == job_id
            assert db.get(PublishJob, job_id).status == "pending"
        finally:
            db.close()
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_publish_job_cancel_transitions_pending_or_scheduled_and_rejects_locked(tmp_path):
    from backend.app.core.database import get_db
    from backend.app.models import PublishJob, Task

    db_dependency, owner_token, creator_account_id = _create_creator_account_with_cookie(
        tmp_path, "publish-cancel-owner"
    )
    db = next(app.dependency_overrides[get_db]())
    try:
        pending_job = PublishJob(
            user_id=1,
            platform_account_id=creator_account_id,
            platform="xhs",
            title="Pending title",
            body="Pending body",
            status="pending",
        )
        scheduled_job = PublishJob(
            user_id=1,
            platform_account_id=creator_account_id,
            platform="xhs",
            title="Scheduled title",
            body="Scheduled body",
            publish_mode="scheduled",
            status="scheduled",
            scheduled_at=datetime.utcnow(),
        )
        published_job = PublishJob(
            user_id=1,
            platform_account_id=creator_account_id,
            platform="xhs",
            title="Published title",
            body="Published body",
            status="published",
        )
        db.add_all([pending_job, scheduled_job, published_job])
        db.commit()
        db.refresh(pending_job)
        db.refresh(scheduled_job)
        db.refresh(published_job)
        pending_id = pending_job.id
        scheduled_id = scheduled_job.id
        published_id = published_job.id
    finally:
        db.close()

    try:
        pending_response = client.post(
            f"/api/publish/jobs/{pending_id}/cancel",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        scheduled_response = client.post(
            f"/api/publish/jobs/{scheduled_id}/cancel",
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        locked_response = client.post(
            f"/api/publish/jobs/{published_id}/cancel",
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        assert pending_response.status_code == 200
        assert pending_response.json()["status"] == "cancelled"
        assert scheduled_response.status_code == 200
        assert scheduled_response.json()["status"] == "cancelled"
        assert locked_response.status_code == 400
        assert locked_response.json()["detail"] == "Publish job cannot be cancelled"

        db = next(app.dependency_overrides[get_db]())
        try:
            assert db.get(PublishJob, pending_id).status == "cancelled"
            assert db.get(PublishJob, scheduled_id).status == "cancelled"
            assert db.get(PublishJob, published_id).status == "published"
            assert db.query(Task).filter(Task.task_type == "creator_publish_cancel").count() == 2
        finally:
            db.close()
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_run_due_tasks_requires_authentication(tmp_path):
    db_dependency = _override_database(tmp_path)
    try:
        response = client.post("/api/tasks/run-due?platform=xhs")

        assert response.status_code == 401
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_run_due_tasks_executes_current_user_due_scheduled_publish_jobs(tmp_path):
    from backend.app.api.publish import get_creator_publish_adapter_factory
    from backend.app.core.database import get_db
    from backend.app.core.security import encrypt_text
    from backend.app.core.time import shanghai_now
    from backend.app.models import AccountCookieVersion, PlatformAccount, PublishAsset, PublishJob, Task

    class FakeDuePublishAdapter:
        calls = []

        def __init__(self, cookies):
            self.cookies = cookies

        def post_note(self, note_info):
            self.calls.append({"cookies": self.cookies, "note_info": note_info})
            return {"note_id": "due-note-001"}

    db_dependency, owner_token, owner_account_id = _create_creator_account_with_cookie(
        tmp_path, "due-publish-owner"
    )
    intruder_token = _register_and_get_access_token("due-publish-intruder")
    db = next(app.dependency_overrides[get_db]())
    try:
        now = shanghai_now()
        intruder_account = PlatformAccount(
            user_id=2,
            platform="xhs",
            sub_type="creator",
            external_user_id="intruder-creator",
            nickname="Intruder creator",
            status="active",
        )
        db.add(intruder_account)
        db.flush()
        db.add(
            AccountCookieVersion(
                platform_account_id=intruder_account.id,
                encrypted_cookies=encrypt_text('{"web_session":"intruder-session","a1":"intruder-a1"}'),
            )
        )

        due_job = PublishJob(
            user_id=1,
            platform_account_id=owner_account_id,
            platform="xhs",
            title="Due title",
            body="Due body",
            publish_mode="scheduled",
            status="pending",
            scheduled_at=now - timedelta(minutes=5),
        )
        future_job = PublishJob(
            user_id=1,
            platform_account_id=owner_account_id,
            platform="xhs",
            title="Future title",
            body="Future body",
            publish_mode="scheduled",
            status="pending",
            scheduled_at=now + timedelta(hours=2),
        )
        intruder_due_job = PublishJob(
            user_id=2,
            platform_account_id=intruder_account.id,
            platform="xhs",
            title="Intruder due title",
            body="Intruder due body",
            publish_mode="scheduled",
            status="pending",
            scheduled_at=now - timedelta(minutes=5),
        )
        db.add_all([due_job, future_job, intruder_due_job])
        db.flush()
        db.add_all(
            [
                PublishAsset(
                    publish_job_id=due_job.id,
                    asset_type="image",
                    file_path="storage/media/due.png",
                    upload_status="uploaded",
                    creator_media_id="media-due",
                    creator_upload_info='{"fileIds":"file-due","width":1080,"height":1440}',
                ),
                PublishAsset(
                    publish_job_id=future_job.id,
                    asset_type="image",
                    file_path="storage/media/future.png",
                    upload_status="uploaded",
                    creator_media_id="media-future",
                    creator_upload_info='{"fileIds":"file-future","width":1080,"height":1440}',
                ),
                PublishAsset(
                    publish_job_id=intruder_due_job.id,
                    asset_type="image",
                    file_path="storage/media/intruder.png",
                    upload_status="uploaded",
                    creator_media_id="media-intruder",
                    creator_upload_info='{"fileIds":"file-intruder","width":1080,"height":1440}',
                ),
            ]
        )
        db.commit()
        due_job_id = due_job.id
        future_job_id = future_job.id
        intruder_job_id = intruder_due_job.id
    finally:
        db.close()

    FakeDuePublishAdapter.calls = []
    app.dependency_overrides[get_creator_publish_adapter_factory] = lambda: FakeDuePublishAdapter
    try:
        intruder_response = client.post(
            "/api/tasks/run-due?platform=xhs",
            headers={"Authorization": f"Bearer {intruder_token}"},
        )
        assert intruder_response.status_code == 200
        assert intruder_response.json()["executed_count"] == 1

        owner_response = client.post(
            "/api/tasks/run-due?platform=xhs",
            headers={"Authorization": f"Bearer {owner_token}"},
        )

        assert owner_response.status_code == 200
        payload = owner_response.json()
        assert payload["executed_count"] == 1
        assert payload["failed_count"] == 0
        assert payload["items"][0]["id"] == due_job_id
        assert payload["items"][0]["status"] == "published"
        assert len(FakeDuePublishAdapter.calls) == 2
        owner_call = FakeDuePublishAdapter.calls[-1]
        assert owner_call["cookies"] == "web_session=creator-session; a1=creator-a1"
        assert owner_call["note_info"]["title"] == "Due title"
        assert owner_call["note_info"]["postTime"] is None

        db = next(app.dependency_overrides[get_db]())
        try:
            assert db.get(PublishJob, due_job_id).status == "published"
            assert db.get(PublishJob, due_job_id).external_note_id == "due-note-001"
            assert db.get(PublishJob, future_job_id).status == "pending"
            assert db.get(PublishJob, intruder_job_id).status == "published"
            tasks = db.query(Task).filter(Task.task_type == "creator_publish_scheduler").all()
            assert len(tasks) == 2
            assert {task.user_id for task in tasks} == {1, 2}
        finally:
            db.close()
    finally:
        app.dependency_overrides.pop(get_creator_publish_adapter_factory, None)
        app.dependency_overrides.pop(db_dependency, None)


def test_run_due_publish_jobs_for_all_users_executes_each_due_user(tmp_path):
    from backend.app.core.database import get_db
    from backend.app.core.security import encrypt_text
    from backend.app.models import AccountCookieVersion, PlatformAccount, PublishAsset, PublishJob, Task
    from backend.app.services.scheduler_service import run_due_publish_jobs_for_all_users

    class FakeAllUsersDuePublishAdapter:
        calls = []

        def __init__(self, cookies):
            self.cookies = cookies

        def post_note(self, note_info):
            self.calls.append({"cookies": self.cookies, "note_info": note_info})
            return {"note_id": f"note-{len(self.calls)}"}

    db_dependency, owner_token, owner_account_id = _create_creator_account_with_cookie(
        tmp_path, "all-users-due-owner"
    )
    _register_and_get_access_token("all-users-due-second")
    db = next(app.dependency_overrides[get_db]())
    try:
        second_account = PlatformAccount(
            user_id=2,
            platform="xhs",
            sub_type="creator",
            external_user_id="second-creator",
            nickname="Second creator",
            status="active",
        )
        db.add(second_account)
        db.flush()
        db.add(
            AccountCookieVersion(
                platform_account_id=second_account.id,
                encrypted_cookies=encrypt_text('{"web_session":"second-session","a1":"second-a1"}'),
            )
        )
        first_job = PublishJob(
            user_id=1,
            platform_account_id=owner_account_id,
            platform="xhs",
            title="First due",
            body="First body",
            publish_mode="scheduled",
            status="pending",
            scheduled_at=datetime.utcnow() - timedelta(minutes=10),
        )
        second_job = PublishJob(
            user_id=2,
            platform_account_id=second_account.id,
            platform="xhs",
            title="Second due",
            body="Second body",
            publish_mode="scheduled",
            status="pending",
            scheduled_at=datetime.utcnow() - timedelta(minutes=8),
        )
        db.add_all([first_job, second_job])
        db.flush()
        db.add_all(
            [
                PublishAsset(
                    publish_job_id=first_job.id,
                    asset_type="image",
                    file_path="storage/media/first.png",
                    upload_status="uploaded",
                    creator_media_id="first-media",
                    creator_upload_info='{"fileIds":"first-file"}',
                ),
                PublishAsset(
                    publish_job_id=second_job.id,
                    asset_type="image",
                    file_path="storage/media/second.png",
                    upload_status="uploaded",
                    creator_media_id="second-media",
                    creator_upload_info='{"fileIds":"second-file"}',
                ),
            ]
        )
        db.commit()
        first_job_id = first_job.id
        second_job_id = second_job.id
    finally:
        db.close()

    FakeAllUsersDuePublishAdapter.calls = []
    try:
        db = next(app.dependency_overrides[get_db]())
        try:
            result = run_due_publish_jobs_for_all_users(
                db=db,
                now=datetime.utcnow(),
                platform="xhs",
                adapter_factory=FakeAllUsersDuePublishAdapter,
            )

            assert result["executed_count"] == 2
            assert result["failed_count"] == 0
            assert {item["id"] for item in result["items"]} == {first_job_id, second_job_id}
            assert db.get(PublishJob, first_job_id).status == "published"
            assert db.get(PublishJob, second_job_id).status == "published"
            assert db.query(Task).filter(Task.task_type == "creator_publish_scheduler").count() == 2
        finally:
            db.close()
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_due_publish_scheduler_registers_interval_job():
    from backend.app.services.scheduler_service import build_due_publish_scheduler, shutdown_due_publish_scheduler

    scheduler = build_due_publish_scheduler(interval_seconds=17, job_func=lambda: None)

    try:
        jobs = scheduler.get_jobs()
        assert {job.id for job in jobs} == {"due_publish_runner", "monitoring_refresh_runner", "auto_tasks_runner", "cookie_health_checker"}
        job_intervals = {job.id: job.trigger.interval.total_seconds() for job in jobs}
        assert job_intervals["due_publish_runner"] == 17
        assert job_intervals["monitoring_refresh_runner"] == 17
        assert job_intervals["auto_tasks_runner"] == 60
        assert job_intervals["cookie_health_checker"] == 7200
    finally:
        shutdown_due_publish_scheduler(scheduler)


def test_run_monitoring_refresh_for_all_users_refreshes_active_targets(tmp_path):
    from backend.app.core.database import get_db
    from backend.app.models import MonitoringSnapshot, MonitoringTarget, Note, PlatformAccount, Task
    from backend.app.services.scheduler_service import run_monitoring_refresh_for_all_users

    db_dependency, owner_token, owner_account_id = _create_pc_account_with_cookie(
        tmp_path, "scheduled-monitor-owner"
    )
    _register_and_get_access_token("scheduled-monitor-second")
    db = next(app.dependency_overrides[get_db]())
    try:
        second_account = PlatformAccount(
            user_id=2,
            platform="xhs",
            sub_type="pc",
            external_user_id="second-pc",
            nickname="Second PC",
            status="active",
        )
        db.add(second_account)
        db.flush()
        db.add_all(
            [
                Note(
                    user_id=1,
                    platform_account_id=owner_account_id,
                    platform="xhs",
                    note_id="monitor-auto-owner",
                    title="低卡早餐自动监控",
                    content="适合通勤的低卡早餐",
                    author_name="owner-author",
                    raw_json={"likes": 20, "collects": 5, "comments": 2, "shares": 1},
                ),
                Note(
                    user_id=2,
                    platform_account_id=second_account.id,
                    platform="xhs",
                    note_id="monitor-auto-second",
                    title="低卡早餐第二用户",
                    content="第二用户的低卡早餐",
                    author_name="second-author",
                    raw_json={"likes": 100},
                ),
            ]
        )
        active_owner = MonitoringTarget(
            user_id=1,
            platform="xhs",
            target_type="keyword",
            name="Owner breakfast",
            value="低卡早餐",
            status="active",
        )
        paused_owner = MonitoringTarget(
            user_id=1,
            platform="xhs",
            target_type="keyword",
            name="Paused breakfast",
            value="低卡早餐",
            status="paused",
        )
        active_second = MonitoringTarget(
            user_id=2,
            platform="xhs",
            target_type="keyword",
            name="Second breakfast",
            value="低卡早餐",
            status="active",
        )
        db.add_all([active_owner, paused_owner, active_second])
        db.commit()
        active_owner_id = active_owner.id
        paused_owner_id = paused_owner.id
        active_second_id = active_second.id
    finally:
        db.close()

    try:
        db = next(app.dependency_overrides[get_db]())
        try:
            result = run_monitoring_refresh_for_all_users(db=db, now=datetime.utcnow(), platform="xhs")

            assert result["refreshed_count"] == 2
            assert result["items"][0]["target_id"] in {active_owner_id, active_second_id}
            assert db.get(MonitoringTarget, active_owner_id).last_refreshed_at is not None
            assert db.get(MonitoringTarget, active_second_id).last_refreshed_at is not None
            assert db.get(MonitoringTarget, paused_owner_id).last_refreshed_at is None
            owner_snapshot = db.scalars(
                select(MonitoringSnapshot).where(MonitoringSnapshot.target_id == active_owner_id)
            ).one()
            second_snapshot = db.scalars(
                select(MonitoringSnapshot).where(MonitoringSnapshot.target_id == active_second_id)
            ).one()
            assert owner_snapshot.payload["matched_count"] == 1
            assert owner_snapshot.payload["total_engagement"] == 28
            assert second_snapshot.payload["matched_count"] == 1
            assert second_snapshot.payload["total_engagement"] == 100
            tasks = db.query(Task).filter(Task.task_type == "monitoring_refresh").all()
            assert len(tasks) == 2
            assert {task.user_id for task in tasks} == {1, 2}
            assert all(task.status == "completed" for task in tasks)
        finally:
            db.close()
    finally:
        app.dependency_overrides.pop(db_dependency, None)
