import pytest
from flask import Flask, session, url_for
from unittest.mock import patch, MagicMock
import pandas as pd
from io import BytesIO

@pytest.fixture
def app():
    from website import create_app
    app = create_app()
    app.config['TESTING'] = True
    
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def auth_session(client):
    with client.session_transaction() as sess:
        sess['email'] = 'test@example.com'
    return client

@pytest.fixture(autouse=True)
def authenticate(client):
    with client.session_transaction() as sess:
        sess['email'] = "test@example.com"
    with patch('db.email_is_verified', return_value=True):
        yield

def test_topics_route(auth_session):
    mock_user = {'email': 'test@example.com', 'is_admin': False}
    mock_topics = [{'id': 1, 'title': 'Test Topic'}]
    
    with patch('db.get_user', return_value=mock_user), \
         patch('db.get_topics', return_value=mock_topics):
        response = auth_session.get('/topics')
        assert response.status_code == 200
        assert b'Test Topic' in response.data

def test_flashcard_route(auth_session):
    mock_topic = {
        'id': 1,
        'title': 'Test Topic',
        'questions': [{'id': 1, 'question': 'Q1', 'answer': 'A1'}]
    }
    
    with patch('db.get_topic', return_value=mock_topic), \
         patch('db.has_access_to_topic', return_value=True):
        response = auth_session.get('/flash/1/1')
        assert response.status_code == 200
        assert b'Q1' in response.data

def test_quiz_route(auth_session):
    mock_topic = {
        'id': 1,
        'title': 'Test Topic',
        'questions': [{'id': 1, 'question': 'Q1', 'answer': 'A1'}]
    }
    
    with patch('db.get_topic', return_value=mock_topic), \
         patch('db.has_access_to_topic', return_value=True), \
         patch('db.generate_quiz', return_value='quiz123'), \
         patch('db.get_last_quiz', return_value=None):
        response = auth_session.get('/quiz/1')
        assert response.status_code == 302  # Redirect to quizlet

def test_quizlet_route(auth_session):
    mock_quiz = {
        'topic_id': 1,
        'questions': [{'id': 1, 'question': 'Q1', 'answer': 'A1'}]
    }
    mock_topic = {'id': 1, 'title': 'Test Topic'}
    
    with patch('db.has_access_to_quiz', return_value=True), \
         patch('db.get_quiz', return_value=mock_quiz), \
         patch('db.get_topic', return_value=mock_topic), \
         patch('db.get_streak', return_value=0):
        response = auth_session.get('/quizlet/quiz123/1')
        assert response.status_code == 200
        assert b'Q1' in response.data

def test_answer_quizlet_valid(auth_session):
    with patch('db.has_access_to_quiz', return_value=True), \
         patch('db.update_quiz_response') as mock_update, \
         patch('db.finish_quiz'):
        mock_update.return_value = {'id': 2}
        response = auth_session.get('/answer-quizlet/quiz123/1?response=yes')
        assert response.status_code == 302  # Redirect to next question

@patch('db.has_access_to_quiz')
def test_answer_quizlet_invalid(mock_has_access, auth_session):
    mock_has_access.return_value = True
    response = auth_session.get('/answer-quizlet/67f73c52dc9057559c189519/1?response=maybe')
    assert response.status_code == 400

def test_add_topic_get(auth_session):
    response = auth_session.get('/add-topic')
    assert response.status_code == 200
    assert b'Add New Topic' in response.data

def test_add_topic_post(auth_session):
    with patch('db.add_topic'):
        response = auth_session.post('/add-topic', data={
            'title': 'New Topic',
            'questions[]': ['Q1', 'Q2'],
            'answers[]': ['A1', 'A2']
        })
        assert response.status_code == 302  # Redirect to topics

def test_edit_topic_get(auth_session):
    mock_topic = {
        'id': 1,
        'title': 'Test Topic',
        'questions': [{'id': 1, 'question': 'Q1', 'answer': 'A1'}]
    }
    
    with patch('db.get_topic', return_value=mock_topic), \
         patch('db.has_access_to_topic', return_value=True):
        response = auth_session.get('/edit-topic/1')
        assert response.status_code == 200
        assert b'Edit Topic' in response.data

def test_delete_topic(auth_session):
    mock_topic = {'id': 1, 'title': 'Test Topic'}
    
    with patch('db.get_topic', return_value=mock_topic), \
         patch('db.has_access_to_topic', return_value=True), \
         patch('db.delete_topic'):
        response = auth_session.get('/delete-topic/1')
        assert response.status_code == 302  # Redirect to topics

def test_export_csv(auth_session):
    mock_topic = {
        'id': 1,
        'title': 'Test Topic',
        'questions': [{'id': 1, 'question': 'Q1', 'answer': 'A1', 'confidence': 50}]
    }
    
    with patch('db.get_topic', return_value=mock_topic), \
         patch('db.has_access_to_topic', return_value=True):
        response = auth_session.get('/export-csv/1')
        assert response.status_code == 200
        assert response.mimetype == 'text/csv'
        content = response.data.decode('utf-8')
        assert 'Q1,A1,50' in content

def test_import_topic_post(auth_session):
    test_file = BytesIO(b"question,answer\r\nQ1,A1\r\n")
    test_file.filename = "test.csv"
    
    with patch('db.import_topic', return_value=1), patch('pandas.read_csv', return_value=pd.DataFrame({'question': ['Q1'], 'answer': ['A1']})):
        response = auth_session.post('/import-topic', data={
            'title': 'Imported Topic',
            'file': (test_file, test_file.filename)
        }, content_type='multipart/form-data')
        assert response.status_code == 200

def test_submit_confidence(auth_session):
    with patch('db.update_confidence', return_value=True):
        response = auth_session.post('/submitconfidence', json={
            'tid': '1',
            'qid': '1',
            'confidence': 75
        })
        assert response.status_code == 200
        assert b'success' in response.data

def test_flash_card_infinite(auth_session):
    mock_topic = {
        'id': 1,
        'title': 'Test Topic',
        'questions': [{'id': 1, 'question': 'Q1', 'answer': 'A1'}]
    }
    
    with patch('db.get_topic', return_value=mock_topic), \
         patch('db.has_access_to_topic', return_value=True):
        response = auth_session.get('/flash/1')
        assert response.status_code == 302  # Redirect to random question