import pytest
from flask import request
from werkzeug.exceptions import NotFound
from unittest.mock import patch, MagicMock
from datetime import datetime

# Setup Flask test app
@pytest.fixture
def app():
    from website import create_app
    app = create_app()
    app.config['TESTING'] = True
    
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture(autouse=True)
def authenticate(client):
    with client.session_transaction() as sess:
        sess['email'] = "test@example.com"
    with patch('db.is_admin', return_value=True), patch('db.email_is_verified', return_value=True):
        yield

def test_server_dashboard(client, monkeypatch):
    mock_get_user_count = MagicMock(return_value=100)
    mock_get_topics_count = MagicMock(return_value=50)
    
    monkeypatch.setattr('db.get_user_count', mock_get_user_count)
    monkeypatch.setattr('db.get_topics_count', mock_get_topics_count)
    
    response = client.get('/admin/')
    assert response.status_code == 200
    assert b'Server Controls' in response.data
    mock_get_user_count.assert_called_once()
    mock_get_topics_count.assert_called_once()

def test_users_view_no_search(client, monkeypatch):
    mock_search_users = MagicMock(return_value=[{'name': 'Test User'}])
    monkeypatch.setattr('db.search_users', mock_search_users)
    
    response = client.get('/admin/users')
    
    assert response.status_code == 200
    assert b'User Management' in response.data
    assert b'Test User' in response.data
    mock_search_users.assert_called_once_with('')

def test_users_view_with_search(client, monkeypatch):
    mock_search_users = MagicMock(return_value=[{'name': 'Test User'}])
    monkeypatch.setattr('db.search_users', mock_search_users)
    
    response = client.get('/admin/users?search=test')
    
    assert response.status_code == 200
    mock_search_users.assert_called_once_with('test')

def test_edit_user_get(client, monkeypatch):
    mock_user = {'_id': '123', 'name': 'Test User'}
    mock_get_user_by_id = MagicMock(return_value=mock_user)
    monkeypatch.setattr('db.get_user_by_id', mock_get_user_by_id)
    
    response = client.get('/admin/users/edit/123')
    
    assert response.status_code == 200
    assert b'Edit User' in response.data
    mock_get_user_by_id.assert_called_once_with('123')

def test_edit_user_get_not_found(client, monkeypatch):
    mock_get_user_by_id = MagicMock(return_value=None)
    monkeypatch.setattr('db.get_user_by_id', mock_get_user_by_id)
    response = client.get('/admin/users/edit/999')
    assert response.status_code == 404

def test_edit_user_post(client, monkeypatch):
    mock_user = {'_id': '123', 'email': 'old@test.com'}
    mock_get_user_by_id = MagicMock(return_value=mock_user)
    mock_edit_user = MagicMock()
    mock_get_user = MagicMock(return_value={'_id': '456'})  # Different user
    
    monkeypatch.setattr('db.get_user_by_id', mock_get_user_by_id)
    monkeypatch.setattr('db.edit_user', mock_edit_user)
    monkeypatch.setattr('db.get_user', mock_get_user)
    
    with client.session_transaction() as sess:
        sess['email'] = 'admin@test.com'
    
    response = client.post('/admin/users/edit/123', data={
        'email': 'new@test.com',
        'name': 'Updated User'
    })
    
    assert response.status_code == 302
    assert response.location.endswith('/admin/users')
    mock_edit_user.assert_called_once_with('123', request)
    # Session email shouldn't change since we're editing a different user
    with client.session_transaction() as sess:
        assert sess['email'] == 'admin@test.com'

def test_edit_user_post_self(client, monkeypatch):
    mock_user = {'_id': '123', 'email': 'old@test.com'}
    mock_get_user_by_id = MagicMock(return_value=mock_user)
    mock_edit_user = MagicMock()
    mock_get_user = MagicMock(return_value={'_id': '123'})  # Same user
    
    monkeypatch.setattr('db.get_user_by_id', mock_get_user_by_id)
    monkeypatch.setattr('db.edit_user', mock_edit_user)
    monkeypatch.setattr('db.get_user', mock_get_user)
    
    with client.session_transaction() as sess:
        sess['email'] = 'old@test.com'
    
    response = client.post('/admin/users/edit/123', data={
        'email': 'new@test.com',
        'name': 'Updated User'
    })
    
    assert response.status_code == 302
    # Session email should update since we're editing our own account
    with client.session_transaction() as sess:
        assert sess['email'] == 'new@test.com'

def test_verify_user(client, monkeypatch):
    mock_verify_user = MagicMock()
    monkeypatch.setattr('db.verify_user', mock_verify_user)
    
    response = client.get('/admin/users/verify/123')
    
    assert response.status_code == 302
    assert response.location.endswith('/admin/users')
    mock_verify_user.assert_called_once_with('123')

def test_delete_user(client, monkeypatch):
    mock_delete_user = MagicMock()
    monkeypatch.setattr('db.delete_user', mock_delete_user)
    
    response = client.post('/admin/users/delete/123')
    
    assert response.status_code == 302
    assert response.location.endswith('/admin/users')
    mock_delete_user.assert_called_once_with('123')

def test_manage_topics_no_search(client, monkeypatch):
    mock_topics = [{'_id': '1', 'title': 'Test Topic'}]
    mock_search_topics = MagicMock(return_value=mock_topics)
    mock_get_topic_holders = MagicMock(return_value='Test User')
    
    monkeypatch.setattr('db.search_topics', mock_search_topics)
    monkeypatch.setattr('db.get_topic_holders', mock_get_topic_holders)
    
    response = client.get('/admin/topics')
    
    assert response.status_code == 200
    assert b'Topics' in response.data
    mock_search_topics.assert_called_once_with('')
    mock_get_topic_holders.assert_called_once_with('1')

def test_manage_topics_with_search(client, monkeypatch):
    mock_search_topics = MagicMock(return_value=[])
    monkeypatch.setattr('db.search_topics', mock_search_topics)
    
    response = client.get('/admin/topics?search=test')
    
    assert response.status_code == 200
    mock_search_topics.assert_called_once_with('test')

def test_admin_delete_topic(client, monkeypatch):
    mock_delete_topic = MagicMock(return_value=True)
    monkeypatch.setattr('db.delete_topic', mock_delete_topic)
    
    response = client.post('/admin/topics/delete/123')
    
    assert response.status_code == 302
    assert response.location.endswith('/admin/topics')
    mock_delete_topic.assert_called_once_with('123')

def test_security_logs_no_filters(client, monkeypatch):
    mock_logs = [{'event': 'login', 'severity': 'medium', 'timestamp': datetime.now()}]
    mock_search_security_logs = MagicMock(return_value=mock_logs)
    monkeypatch.setattr('db.search_security_logs', mock_search_security_logs)
    
    response = client.get('/admin/security-logs')
    
    assert response.status_code == 200
    assert b'Security Logs' in response.data
    mock_search_security_logs.assert_called_once_with('', 'all')

def test_security_logs_with_filters(client, monkeypatch):
    mock_search_security_logs = MagicMock(return_value=[])
    monkeypatch.setattr('db.search_security_logs', mock_search_security_logs)
    
    response = client.get('/admin/security-logs?search=failed&severity=high')
    
    assert response.status_code == 200
    mock_search_security_logs.assert_called_once_with('failed', 'high')

def test_ip_lookup(client):
    mock_response = {
        'status': 'success',
        'country': 'United States',
        'city': 'New York'
    }
    
    with patch('requests.get') as mock_get:
        mock_get.return_value.raise_for_status.return_value = None
        mock_get.return_value.json.return_value = mock_response
        
        response = client.get('/admin/ip-lookup/8.8.8.8')
        
        assert response.status_code == 200
        assert response.json == mock_response
        mock_get.assert_called_once_with('http://ip-api.com/json/8.8.8.8')