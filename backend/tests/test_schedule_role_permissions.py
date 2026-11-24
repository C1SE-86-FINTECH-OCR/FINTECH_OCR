from datetime import datetime, timedelta, timezone
from app.models import User, Schedule
from tests.test_phase2_api import api_env, _token


def test_schedule_role_permissions(api_env):
    client, users, password = api_env
    admin = _token(client, "admin@phase2.test", password)
    accountant = _token(client, "accountant@phase2.test", password)
    emp1 = _token(client, "employee1@phase2.test", password)
    emp2 = _token(client, "employee2@phase2.test", password)

    emp1_id = users["employee1@phase2.test"]
    emp2_id = users["employee2@phase2.test"]
    now = datetime.now(timezone.utc)

    # 1. Accountant cannot create schedule (403)
    resp = client.post(
        "/api/v1/schedules",
        headers={"Authorization": f"Bearer {accountant}"},
        json={
            "title": "Accountant create trip",
            "destination": "HN",
            "starts_at": (now + timedelta(days=10)).isoformat(),
            "ends_at": (now + timedelta(days=11)).isoformat(),
            "assigned_to": emp1_id,
        },
    )
    assert resp.status_code == 403
    assert "Kế toán chỉ có quyền xem" in resp.json()["detail"]

    # 2. Employee cannot create schedule even for themselves (403)
    resp = client.post(
        "/api/v1/schedules",
        headers={"Authorization": f"Bearer {emp1}"},
        json={
            "title": "Emp1 own trip attempt",
            "destination": "Da Nang",
            "starts_at": (now + timedelta(days=14)).isoformat(),
            "ends_at": (now + timedelta(days=15)).isoformat(),
            "assigned_to": emp1_id,
            "notes": "My self-scheduled trip",
        },
    )
    assert resp.status_code == 403
    assert "quản trị viên" in resp.json()["detail"].lower()

    # 3. Admin creates schedule assigned to Employee (201)
    resp = client.post(
        "/api/v1/schedules",
        headers={"Authorization": f"Bearer {admin}"},
        json={
            "title": "Admin assigned trip to Emp1",
            "destination": "Da Nang",
            "starts_at": (now + timedelta(days=14)).isoformat(),
            "ends_at": (now + timedelta(days=15)).isoformat(),
            "assigned_to": emp1_id,
            "notes": "Admin assigned trip",
        },
    )
    assert resp.status_code == 201
    own_trip_id = resp.json()["id"]

    # 4. Admin can create schedule for any active employee (201)
    resp = client.post(
        "/api/v1/schedules",
        headers={"Authorization": f"Bearer {admin}"},
        json={
            "title": "Admin assigned trip",
            "destination": "Can Tho",
            "starts_at": (now + timedelta(days=16)).isoformat(),
            "ends_at": (now + timedelta(days=17)).isoformat(),
            "assigned_to": emp2_id,
        },
    )
    assert resp.status_code == 201
    admin_trip_id = resp.json()["id"]

    # 5. Accountant cannot update schedule (403)
    resp = client.patch(
        f"/api/v1/schedules/{own_trip_id}",
        headers={"Authorization": f"Bearer {accountant}"},
        json={"notes": "Accountant edit"},
    )
    assert resp.status_code == 403
    assert "Kế toán chỉ có quyền xem" in resp.json()["detail"]

    # 6. Employee cannot update another employee's schedule (403)
    resp = client.patch(
        f"/api/v1/schedules/{admin_trip_id}",
        headers={"Authorization": f"Bearer {emp1}"},
        json={"notes": "Emp1 tries to edit Emp2 trip"},
    )
    assert resp.status_code == 403
    assert "chính mình" in resp.json()["detail"]

    # 7. Employee cannot reassign their own schedule to someone else (403)
    resp = client.patch(
        f"/api/v1/schedules/{own_trip_id}",
        headers={"Authorization": f"Bearer {emp1}"},
        json={"assigned_to": emp2_id},
    )
    assert resp.status_code == 403
    assert "không thể chuyển giao" in resp.json()["detail"]

    # 8. Employee CAN update their own schedule (200)
    resp = client.patch(
        f"/api/v1/schedules/{own_trip_id}",
        headers={"Authorization": f"Bearer {emp1}"},
        json={
            "destination": "Da Nang Updated",
            "notes": "Updated notes by myself",
            "status": "completed",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["destination"] == "Da Nang Updated"
    assert resp.json()["status"] == "completed"

    # 9. Admin CAN update any schedule (200)
    resp = client.patch(
        f"/api/v1/schedules/{admin_trip_id}",
        headers={"Authorization": f"Bearer {admin}"},
        json={"destination": "Can Tho Central", "status": "completed"},
    )
    assert resp.status_code == 200
    assert resp.json()["destination"] == "Can Tho Central"

    # 10. Accountant CAN view all schedules (200)
    resp = client.get(
        "/api/v1/schedules",
        headers={"Authorization": f"Bearer {accountant}"},
    )
    assert resp.status_code == 200
    all_ids = [item["id"] for item in resp.json()]
    assert own_trip_id in all_ids
    assert admin_trip_id in all_ids
