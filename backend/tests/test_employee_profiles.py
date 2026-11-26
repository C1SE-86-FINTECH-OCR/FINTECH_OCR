from types import SimpleNamespace
from app.main import employee_profile_data


def test_employee_profile_hides_contact_and_account_status_from_other_employees():
    target=SimpleNamespace(id=4,full_name='Employee',role='employee',email='private@example.com',status='active')
    scores=[{'user_id':2,'completed':3,'rank':1},{'user_id':4,'completed':3,'rank':1}]
    data=employee_profile_data(target,SimpleNamespace(id=9,role='employee'),scores)
    assert data['rank']==1 and data['completed_trips']==3
    assert 'email' not in data and 'status' not in data
    for viewer in [SimpleNamespace(id=4,role='employee'),SimpleNamespace(id=9,role='admin'),SimpleNamespace(id=9,role='accountant')]:
        assert employee_profile_data(target,viewer,scores)['email']=='private@example.com'


def test_unranked_employee_has_zero_completed_trips():
    target=SimpleNamespace(id=4,full_name='Employee',role='employee',email='private@example.com',status='active')
    data=employee_profile_data(target,SimpleNamespace(id=9,role='employee'),[])
    assert data['rank'] is None and data['completed_trips']==0
