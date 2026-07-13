from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import sessionmaker

from backend.app.main import app


client = TestClient(app)


def _override_database(tmp_path, name="admin-test.db"):
    from backend.app.core.database import Base, get_db

    engine = create_engine(
        f"sqlite:///{tmp_path / name}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return get_db, testing_session


def _register(username: str) -> dict:
    response = client.post(
        "/api/auth/register",
        json={"username": username, "password": "secret123"},
    )
    assert response.status_code == 200
    return response.json()


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_concurrent_registration_creates_exactly_one_first_admin(tmp_path):
    from backend.app.models import User

    db_dependency, testing_session = _override_database(tmp_path, "concurrent-register.db")
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(_register, ("first-operator", "second-operator")))

        assert sum(item["user"]["is_admin"] for item in responses) == 1
        assert all(item["user"]["is_active"] for item in responses)
        with testing_session() as db:
            users = db.scalars(select(User).order_by(User.id)).all()
            assert len(users) == 2
            assert sum(user.is_admin for user in users) == 1
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_mysql_registration_lock_releases_on_the_same_connection():
    from backend.app.api.auth import _lock_user_registration, _unlock_user_registration

    class FakeConnection:
        def __init__(self):
            self.statements = []
            self.closed = False
            self.invalidated = False

        def scalar(self, statement):
            self.statements.append(str(statement))
            return 1

        def invalidate(self):
            self.invalidated = True

        def close(self):
            self.closed = True

    class FakeEngine:
        dialect = type("Dialect", (), {"name": "mysql"})()

        def __init__(self, connection):
            self.connection = connection

        def connect(self):
            return self.connection

    connection = FakeConnection()
    engine = FakeEngine(connection)
    fake_db = type("FakeSession", (), {"get_bind": lambda self: engine})()

    acquired_connection = _lock_user_registration(fake_db)
    _unlock_user_registration(acquired_connection)

    assert acquired_connection is connection
    assert connection.statements == [
        "SELECT GET_LOCK('xhs_user_registration', 10)",
        "SELECT RELEASE_LOCK('xhs_user_registration')",
    ]
    assert connection.closed is True
    assert connection.invalidated is False


def test_admin_guard_user_updates_and_disabled_authentication(tmp_path):
    db_dependency, _ = _override_database(tmp_path)
    try:
        admin = _register("admin-user")
        member = _register("member-user")
        admin_headers = _headers(admin["access_token"])
        member_headers = _headers(member["access_token"])

        assert admin["user"] == {
            "id": 1,
            "username": "admin-user",
            "is_admin": True,
            "is_active": True,
        }
        assert member["user"]["is_admin"] is False
        assert client.get("/api/admin/overview").status_code == 401
        assert client.get("/api/admin/overview", headers=member_headers).status_code == 403

        users_response = client.get("/api/admin/users", headers=admin_headers)
        assert users_response.status_code == 200
        assert users_response.json()["total"] == 2
        assert all(item["last_login_at"] for item in users_response.json()["items"])

        disable_response = client.patch(
            f"/api/admin/users/{member['user']['id']}",
            headers=admin_headers,
            json={"is_active": False},
        )
        assert disable_response.status_code == 200
        assert disable_response.json()["is_active"] is False

        assert client.get("/api/auth/me", headers=member_headers).status_code == 403
        assert client.post(
            "/api/auth/login",
            json={"username": "member-user", "password": "secret123"},
        ).status_code == 403
        assert client.post(
            "/api/auth/refresh",
            json={"refresh_token": member["refresh_token"]},
        ).status_code == 403

        self_disable = client.patch(
            f"/api/admin/users/{admin['user']['id']}",
            headers=admin_headers,
            json={"is_active": False},
        )
        assert self_disable.status_code == 400
        self_demote = client.patch(
            f"/api/admin/users/{admin['user']['id']}",
            headers=admin_headers,
            json={"is_admin": False},
        )
        assert self_demote.status_code == 400
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_concurrent_admin_updates_keep_one_effective_admin(tmp_path):
    from backend.app.models import User

    db_dependency, testing_session = _override_database(tmp_path, "concurrent-admin-update.db")
    try:
        first = _register("first-admin")
        second = _register("second-admin")
        promote = client.patch(
            f"/api/admin/users/{second['user']['id']}",
            headers=_headers(first["access_token"]),
            json={"is_admin": True},
        )
        assert promote.status_code == 200

        def disable_other(actor: dict, target: dict):
            return client.patch(
                f"/api/admin/users/{target['user']['id']}",
                headers=_headers(actor["access_token"]),
                json={"is_active": False},
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = [
                executor.submit(disable_other, first, second),
                executor.submit(disable_other, second, first),
            ]
            status_codes = [future.result().status_code for future in responses]

        assert sorted(status_codes) == [200, 403]
        with testing_session() as db:
            effective_admins = db.scalars(
                select(User).where(User.is_admin.is_(True), User.is_active.is_(True))
            ).all()
            assert len(effective_admins) == 1
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_admin_read_models_are_global_paginated_and_secret_safe(tmp_path):
    from backend.app.models import (
        AiDraft,
        AiGeneratedAsset,
        ModelConfig,
        Note,
        PlatformAccount,
        PublishJob,
        Task,
    )

    db_dependency, testing_session = _override_database(tmp_path)
    try:
        admin = _register("global-admin")
        member = _register("content-owner")
        with testing_session() as db:
            account = PlatformAccount(
                user_id=member["user"]["id"],
                platform="xhs",
                sub_type="pc",
                nickname="Owner account",
                status="active",
            )
            db.add(account)
            db.flush()
            db.add_all([
                Note(
                    user_id=member["user"]["id"],
                    platform_account_id=account.id,
                    platform="xhs",
                    note_id="admin-note-1",
                    title="Saved note",
                ),
                AiDraft(
                    user_id=member["user"]["id"],
                    platform="xhs",
                    title="Draft title",
                ),
                AiGeneratedAsset(
                    user_id=member["user"]["id"],
                    prompt="Generated cover",
                    model_name="image-model",
                    file_path="storage/generated.png",
                ),
                PublishJob(
                    user_id=member["user"]["id"],
                    platform_account_id=account.id,
                    platform="xhs",
                    title="Published title",
                    status="published",
                    published_at=datetime.now(),
                ),
                Task(
                    user_id=member["user"]["id"],
                    platform="xhs",
                    task_type="crawl",
                    status="completed",
                    progress=100,
                ),
                ModelConfig(
                    user_id=member["user"]["id"],
                    name="Owner text model",
                    model_type="text",
                    provider="openai-compatible",
                    model_name="gpt-test",
                    base_url="https://example.test/v1",
                    encrypted_api_key="encrypted-secret-value",
                ),
            ])
            db.commit()

        headers = _headers(admin["access_token"])
        accounts = client.get("/api/admin/platform-accounts?q=content-owner", headers=headers).json()
        assert accounts["total"] == 1
        assert accounts["items"][0]["username"] == "content-owner"

        summary = client.get("/api/admin/content/summary", headers=headers).json()
        assert summary == {
            "total": 4,
            "notes": 1,
            "drafts": 1,
            "generated_assets": 1,
            "publish_jobs": 1,
            "publish_statuses": {"published": 1},
        }
        content = client.get("/api/admin/content?type=draft", headers=headers).json()
        assert content["total"] == 1
        assert content["items"][0]["content_type"] == "draft"

        tasks = client.get("/api/admin/tasks?q=content-owner", headers=headers).json()
        assert tasks["total"] == 1
        assert tasks["items"][0]["user_id"] == member["user"]["id"]

        configs = client.get("/api/admin/model-configs?status=configured", headers=headers).json()
        assert configs["total"] == 1
        assert configs["items"][0]["has_api_key"] is True
        assert "encrypted_api_key" not in configs["items"][0]
        assert "api_key" not in configs["items"][0]

        overview = client.get("/api/admin/overview", headers=headers).json()
        assert overview["users"]["total"] == 2
        assert overview["content"]["total"] == 4
        assert overview["models"]["configured"] == 1
        assert overview["recent_activity"]

        health = client.get("/api/admin/system-health", headers=headers)
        assert health.status_code == 200
        assert health.json()["database"]["status"] == "healthy"
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_schedulers_skip_disabled_users(tmp_path, monkeypatch):
    from backend.app.models import AutoTask, MonitoringTarget, PlatformAccount, PublishJob, User
    from backend.app.services import scheduler_service

    db_dependency, testing_session = _override_database(tmp_path)
    try:
        _register("active-admin")
        disabled = _register("disabled-owner")
        with testing_session() as db:
            user = db.get(User, disabled["user"]["id"])
            user.is_active = False
            account = PlatformAccount(
                user_id=user.id,
                platform="xhs",
                sub_type="creator",
                nickname="Disabled account",
                status="active",
            )
            db.add(account)
            db.flush()
            job = PublishJob(
                user_id=user.id,
                platform_account_id=account.id,
                platform="xhs",
                title="Must not publish",
                publish_mode="scheduled",
                status="pending",
                scheduled_at=datetime.now() - timedelta(minutes=5),
            )
            target = MonitoringTarget(
                user_id=user.id,
                platform="xhs",
                target_type="keyword",
                name="Must not refresh",
                value="blocked",
                status="active",
            )
            auto_task = AutoTask(
                user_id=user.id,
                name="Must not run",
                keywords=["blocked"],
                pc_account_id=account.id,
                creator_account_id=account.id,
                schedule_type="interval",
                next_run_at=datetime.now() - timedelta(minutes=5),
                status="active",
            )
            db.add_all([job, target, auto_task])
            db.commit()
            job_id = job.id
            target_id = target.id
            auto_task_id = auto_task.id
            account_id = account.id

        with testing_session() as db:
            publish_result = scheduler_service.run_due_publish_jobs_for_all_users(
                db=db,
                now=datetime.now(),
                platform="xhs",
                adapter_factory=lambda _cookies: (_ for _ in ()).throw(AssertionError("adapter called")),
            )
            monitoring_result = scheduler_service.run_monitoring_refresh_for_all_users(
                db=db,
                now=datetime.now(),
                platform="xhs",
            )
            assert publish_result["executed_count"] == 0
            assert monitoring_result["refreshed_count"] == 0

        monkeypatch.setattr(scheduler_service, "SessionLocal", testing_session)
        scheduler_service.run_due_auto_tasks()
        scheduler_service.check_all_account_cookies_once()

        with testing_session() as db:
            assert db.get(PublishJob, job_id).status == "pending"
            assert db.get(MonitoringTarget, target_id).last_refreshed_at is None
            assert db.get(AutoTask, auto_task_id).next_run_at < datetime.now()
            assert db.get(PlatformAccount, account_id).status == "active"
    finally:
        app.dependency_overrides.pop(db_dependency, None)


def test_legacy_database_without_alembic_version_receives_admin_migration(tmp_path, monkeypatch):
    from backend.app.core import database

    database_path = tmp_path / "legacy.db"
    database_url = f"sqlite:///{database_path}"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE users ("
            "id INTEGER PRIMARY KEY, username VARCHAR(80) NOT NULL UNIQUE, "
            "password_hash VARCHAR(128) NOT NULL, created_at DATETIME NOT NULL)"
        ))
        connection.execute(text(
            "INSERT INTO users (id, username, password_hash, created_at) VALUES "
            "(4, 'legacy-first', 'hash', CURRENT_TIMESTAMP), "
            "(9, 'legacy-second', 'hash', CURRENT_TIMESTAMP)"
        ))

    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database.settings, "database_url", database_url)
    database._run_alembic_migrations()

    assert {column["name"] for column in inspect(engine).get_columns("users")} >= {"is_admin", "is_active", "last_login_at"}
    with engine.connect() as connection:
        rows = connection.execute(text(
            "SELECT id, is_admin, is_active FROM users ORDER BY id"
        )).all()
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert rows == [(4, 1, 1), (9, 0, 1)]
    assert revision == "a4f7c2d9e801"
