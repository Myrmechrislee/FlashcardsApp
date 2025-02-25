import glob, json, os, uuid, shutil, io, csv, hashlib
from pymongo import MongoClient
from bson import ObjectId

client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017/flashcards"))
db = client["flashcards"]
salt = "558f455d7315ce54148b6f0628ae6f3f"

def get_user(email):
    return db.users.find_one({"email": email}, {"topics": 1})

def update_confidence(tid, qid, c):
    return db.topics.update_one({
        "_id": ObjectId(tid),
        "questions.id": qid
        }, 
        {
            "$set": {"questions.$.confidence": c}
        })
def get_topics(email):
    user = get_user(email)
    topic_ids = user["topics"]
    topics = db.topics.find({"_id": {"$in": topic_ids}})
    return topics.to_list()

def has_access_to_topic(email, tid):
    return ObjectId(tid) in get_user(email)["topics"]
def get_topic(id):
    topics = db.topics.find_one({"_id": ObjectId(id)})
    return topics

def add_topic(email, title, questions, answers):
    questions_data = []
    for i, (q, a) in enumerate(zip(questions, answers)):
        questions_data.append(
            {
                "id": i,
                "question": q, 
                "answer": a,
                "confidence": 0
            }
        )
    data = {
        "title": title,
        "questions": questions_data
    }
    res = db.topics.insert_one(data)
    
    db.users.update_one({"email": email}, {"$push": {"topics": res.inserted_id}})
def edit_topic(id, form_data):
    data = get_topic(id)
    data['title'] = form_data['title']
    
    questions = []
    for q_id, (question, answer, confidence) in enumerate(zip( 
                                       form_data.getlist('questions[]'), 
                                       form_data.getlist('answers[]'), form_data.getlist('confidence[]'))):
        questions.append({
            "id": q_id,
            "question": question,
            "answer": answer,
            "confidence": int(confidence)
        })
    print(questions)
    data["questions"] = questions
    db.topics.update_one({"_id": data["_id"]}, {"$set": data})

def delete_topic(id):
    topic = get_topic(id)
    db.backupTopics.insert_one(topic)
    db.topics.delete_one(topic)

def import_topic(email, title, df):
    if "id" not in df.columns:
        df["id"] = range(len(df))
    df["confidence"] = df.get("confidence", 0)
    df = df[["id", "question", "answer", "confidence"]]
    questions = df.to_dict(orient="records")
    data = {
        "title": title,
        "questions": questions
    }
    res = db.topics.insert_one(data)
    db.users.update_one({"email": email}, {"$push": {"topics": res.inserted_id}})
    return len(questions)

def test_login(email, password):
    password_hash = hashlib.md5((salt + password).encode()).hexdigest()
    user = db.users.find_one({"email": email, "password_hash": password_hash})
    if user == None: 
        return False, "" 
    else: 
        return True, user

def add_user(name, email, password):
    password_hash = hashlib.md5((salt + password).encode()).hexdigest()
    db.users.insert_one({
        "name": name,
        "email": email,
        "password_hash": password_hash,
        "topics": []
    })