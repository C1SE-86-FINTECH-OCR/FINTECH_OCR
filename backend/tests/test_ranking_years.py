from datetime import datetime
from zoneinfo import ZoneInfo

from app.models import AuditLog, Schedule
from tests.api_support import _token, api_env


def test_ranking_years_completion_dates_and_ties(api_env):
    client, users, password = api_env
    admin = users['admin@phase2.test']
    accountant = users['accountant@phase2.test']
    first = users['employee1@phase2.test']
    second = users['employee2@phase2.test']
    current_year = datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).year
    path = '/api/v1/ranking'
    initial_headers = {'Authorization': 'Bearer ' + _token(client, 'admin@phase2.test', password)}
    assert client.get(path + '/years', headers=initial_headers).json() == {
        'current_year': current_year,
        'years': list(range(current_year + 5, current_year - 6, -1)),
    }

    with client.app.state.phase2_test_session() as db:
        for assignee, end, completion, status in (
            (first, '2024-12-31T16:59:59', '2024-12-31T17:00:00', 'completed'),
            (first, '2025-02-01T00:00:00', None, 'completed'),
            (second, '2024-12-31T17:00:00', None, 'completed'),
            (second, '2025-06-01T00:00:00', None, 'completed'),
            (accountant, '2025-01-01T00:00:00', None, 'completed'),
            (first, '2025-01-01T00:00:00', '2024-12-31T16:59:59', 'completed'),
            (second, '2024-10-01T00:00:00', None, 'completed'),
            (first, '2023-03-01T00:00:00', None, 'planned'),
            (first, '2025-04-01T00:00:00', '2025-04-01T00:00:00', 'cancelled'),
        ):
            db.add(Schedule(
                title='Trip', destination='Test',
                starts_at=datetime.fromisoformat('2023-01-01T00:00:00'),
                ends_at=datetime.fromisoformat(end),
                completed_at=datetime.fromisoformat(completion) if completion else None,
                assigned_to=assignee, created_by=admin, status=status,
            ))
        demo = Schedule(title='Demo', destination='Test', starts_at=datetime(2025, 2, 1),
                        ends_at=datetime(2025, 2, 2), completed_at=datetime(2025, 2, 2),
                        assigned_to=first, created_by=admin, status='completed')
        db.add(demo)
        db.flush()
        db.add(AuditLog(actor_id=admin, action='schedule.demo_seeded', entity_type='schedule', entity_id=demo.id))
        db.commit()

    assert client.get(path + '/years').status_code == 401
    assert client.get(path, params={'year': 2025}).status_code == 401
    for account in ('admin', 'accountant', 'employee1'):
        headers = {'Authorization': 'Bearer ' + _token(client, f'{account}@phase2.test', password)}

        def scores(**params):
            response = client.get(path, params=params, headers=headers)
            assert response.status_code == 200
            return [(row['user_id'], row['completed'], row['rank']) for row in response.json()]

        response = client.get(path + '/years', headers=headers)
        assert response.status_code == 200
        assert response.json() == {
            'current_year': current_year,
            'years': list(range(current_year + 5, 2022, -1)),
        }
        assert scores(year=2025) == [(first, 2, 1), (second, 2, 1), (accountant, 1, 3)]
        assert scores(year=2024) == [(first, 1, 1), (second, 1, 1)]
        assert scores(year=2023) == []
        if current_year > 2025:
            assert scores(year=current_year) == []
        assert scores(year=current_year + 5) == []
        assert scores(period='all') == [(first, 3, 1), (second, 3, 1), (accountant, 1, 3)]
        assert scores(year=2025) == [(first, 2, 1), (second, 2, 1), (accountant, 1, 3)]
        assert client.get(path, params={'year': 0}, headers=headers).status_code == 422
