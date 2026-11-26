from datetime import datetime, timezone
from app.models import AuditLog, User
from tests.test_phase2_api import api_env, _token


def test_audit_logs_permissions_and_actor_name(api_env):
    client, users, password = api_env
    admin = _token(client, "admin@phase2.test", password)
    accountant = _token(client, "accountant@phase2.test", password)
    emp1 = _token(client, "employee1@phase2.test", password)

    # 1. Unauthenticated gets 401
    assert client.get("/api/v1/audit-logs").status_code == 401

    # 2. Accountant gets 403
    resp = client.get("/api/v1/audit-logs", headers={"Authorization": f"Bearer {accountant}"})
    assert resp.status_code == 403

    # 3. Employee gets 403
    resp = client.get("/api/v1/audit-logs", headers={"Authorization": f"Bearer {emp1}"})
    assert resp.status_code == 403

    # 4. Admin gets 200
    resp = client.get("/api/v1/audit-logs", headers={"Authorization": f"Bearer {admin}"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_audit_logs_actor_name_for_deleted_and_existing_users(api_env):
    client, users, password = api_env
    admin = _token(client, "admin@phase2.test", password)
    admin_id = users["admin@phase2.test"]

    from app.main import app
    with app.state.phase2_test_session() as db:
        log_admin = AuditLog(actor_id=admin_id, action="test.admin_action", entity_type="test", entity_id=1)
        log_deleted = AuditLog(actor_id=999999, action="test.deleted_user_action", entity_type="test", entity_id=2)
        log_none = AuditLog(actor_id=None, action="test.anonymous_action", entity_type="test", entity_id=3)
        db.add_all([log_admin, log_deleted, log_none])
        db.commit()

    resp = client.get("/api/v1/audit-logs", headers={"Authorization": f"Bearer {admin}"})
    assert resp.status_code == 200
    rows = {r["action"]: r for r in resp.json()}

    assert rows["test.admin_action"]["actor_name"] == "Test admin"
    assert rows["test.admin_action"]["actor_id"] == admin_id

    assert rows["test.deleted_user_action"]["actor_name"] == "Không xác định"
    assert rows["test.deleted_user_action"]["actor_id"] == 999999

    assert rows["test.anonymous_action"]["actor_name"] == "Không xác định"
    assert rows["test.anonymous_action"]["actor_id"] is None


def test_audit_logs_date_filter_vietnam_timezone_midnight_boundaries(api_env):
    client, users, password = api_env
    admin = _token(client, "admin@phase2.test", password)
    admin_id = users["admin@phase2.test"]

    # Target date in VN time (UTC+7): 2026-11-27
    # Event A: 2026-11-27 00:05:00 VN -> 2026-11-26 17:05:00 UTC (sát sau nửa đêm 27)
    dt_a = datetime(2026, 11, 26, 17, 5, 0, tzinfo=timezone.utc)
    # Event B: 2026-11-27 23:55:00 VN -> 2026-11-27 16:55:00 UTC (sát trước nửa đêm 27)
    dt_b = datetime(2026, 11, 27, 16, 55, 0, tzinfo=timezone.utc)
    # Event C: 2026-11-26 23:55:00 VN -> 2026-11-26 16:55:00 UTC (hôm trước)
    dt_c = datetime(2026, 11, 26, 16, 55, 0, tzinfo=timezone.utc)
    # Event D: 2026-11-28 00:05:00 VN -> 2026-11-27 17:05:00 UTC (hôm sau)
    dt_d = datetime(2026, 11, 27, 17, 5, 0, tzinfo=timezone.utc)

    from app.main import app
    with app.state.phase2_test_session() as db:
        db.add_all([
            AuditLog(actor_id=admin_id, action="vn_boundary.event_a", entity_type="test", entity_id=101, created_at=dt_a),
            AuditLog(actor_id=admin_id, action="vn_boundary.event_b", entity_type="test", entity_id=102, created_at=dt_b),
            AuditLog(actor_id=admin_id, action="vn_boundary.event_c", entity_type="test", entity_id=103, created_at=dt_c),
            AuditLog(actor_id=admin_id, action="vn_boundary.event_d", entity_type="test", entity_id=104, created_at=dt_d),
        ])
        db.commit()

    # 1. Filter by day=2026-11-27
    resp = client.get("/api/v1/audit-logs?day=2026-11-27", headers={"Authorization": f"Bearer {admin}"})
    assert resp.status_code == 200
    actions_day = {r["action"] for r in resp.json()}
    assert "vn_boundary.event_a" in actions_day
    assert "vn_boundary.event_b" in actions_day
    assert "vn_boundary.event_c" not in actions_day
    assert "vn_boundary.event_d" not in actions_day

    # 2. Filter by period=day&date_value=2026-11-27
    resp = client.get("/api/v1/audit-logs?period=day&date_value=2026-11-27", headers={"Authorization": f"Bearer {admin}"})
    assert resp.status_code == 200
    actions_period = {r["action"] for r in resp.json()}
    assert "vn_boundary.event_a" in actions_period
    assert "vn_boundary.event_b" in actions_period
    assert "vn_boundary.event_c" not in actions_period
    assert "vn_boundary.event_d" not in actions_period

    # 3. Filter by previous day: 2026-11-26
    resp = client.get("/api/v1/audit-logs?day=2026-11-26", headers={"Authorization": f"Bearer {admin}"})
    assert resp.status_code == 200
    actions_prev = {r["action"] for r in resp.json()}
    assert "vn_boundary.event_c" in actions_prev
    assert "vn_boundary.event_a" not in actions_prev
    assert "vn_boundary.event_b" not in actions_prev

    # 4. Filter by month=2026-11
    resp = client.get("/api/v1/audit-logs?month=2026-11", headers={"Authorization": f"Bearer {admin}"})
    assert resp.status_code == 200
    actions_month = {r["action"] for r in resp.json()}
    assert "vn_boundary.event_a" in actions_month
    assert "vn_boundary.event_b" in actions_month
    assert "vn_boundary.event_c" in actions_month
    assert "vn_boundary.event_d" in actions_month

    # 5. Filter by year=2026
    resp = client.get("/api/v1/audit-logs?year=2026", headers={"Authorization": f"Bearer {admin}"})
    assert resp.status_code == 200
    actions_year = {r["action"] for r in resp.json()}
    assert "vn_boundary.event_a" in actions_year
    assert "vn_boundary.event_b" in actions_year
    assert "vn_boundary.event_c" in actions_year
    assert "vn_boundary.event_d" in actions_year

    # 6. Filter by different year: 2025 (should exclude all 2026 events)
    resp = client.get("/api/v1/audit-logs?year=2025", headers={"Authorization": f"Bearer {admin}"})
    assert resp.status_code == 200
    actions_2025 = {r["action"] for r in resp.json()}
    assert not any(a.startswith("vn_boundary.") for a in actions_2025)
