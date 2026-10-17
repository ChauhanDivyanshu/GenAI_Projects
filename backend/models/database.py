# models/database.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class Meeting(db.Model):
    __tablename__ = 'meetings'

    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.String(100), unique=True, nullable=False)
    title = db.Column(db.String(200))
    meeting_type = db.Column(db.String(50))  # interview, meeting, lecture
    platform = db.Column(db.String(50), default='google_meet')
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    duration_minutes = db.Column(db.Float)
    recording_path = db.Column(db.String(500))
    audio_path = db.Column(db.String(500))
    status = db.Column(db.String(20), default='active')  # active, completed, analyzing
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    transcripts = db.relationship('Transcript', backref='meeting', lazy=True)
    notes = db.relationship('MeetingNote', backref='meeting', lazy=True)
    cheating_events = db.relationship('CheatingEvent', backref='meeting', lazy=True)
    participants = db.relationship('Participant', backref='meeting', lazy=True)
    feedback = db.relationship('Feedback', backref='meeting', lazy=True)


class Participant(db.Model):
    __tablename__ = 'participants'

    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('meetings.id'))
    name = db.Column(db.String(100))
    role = db.Column(db.String(50))  # interviewer, candidate, attendee
    email = db.Column(db.String(100))
    join_time = db.Column(db.DateTime)
    leave_time = db.Column(db.DateTime)
    face_image_path = db.Column(db.String(500))


class Transcript(db.Model):
    __tablename__ = 'transcripts'

    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('meetings.id'))
    speaker = db.Column(db.String(100))
    text = db.Column(db.Text)
    timestamp_start = db.Column(db.Float)
    timestamp_end = db.Column(db.Float)
    confidence = db.Column(db.Float)
    is_question = db.Column(db.Boolean, default=False)
    is_answer = db.Column(db.Boolean, default=False)
    sentiment = db.Column(db.String(20))  # positive, negative, neutral
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MeetingNote(db.Model):
    __tablename__ = 'meeting_notes'

    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('meetings.id'))
    note_type = db.Column(db.String(50))  # summary, key_point, action_item, question, answer
    content = db.Column(db.Text)
    timestamp = db.Column(db.Float)
    importance = db.Column(db.String(20))  # high, medium, low
    topic = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CheatingEvent(db.Model):
    __tablename__ = 'cheating_events'

    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('meetings.id'))
    participant_id = db.Column(db.Integer, db.ForeignKey('participants.id'))
    event_type = db.Column(db.String(50))
    # Types: eye_away, tab_switch, multiple_faces, face_absent,
    #         phone_detected, screen_share_suspicious, voice_change
    description = db.Column(db.Text)
    severity = db.Column(db.String(20))  # low, medium, high, critical
    timestamp = db.Column(db.Float)
    screenshot_path = db.Column(db.String(500))
    confidence = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class QAEvaluation(db.Model):
    __tablename__ = 'qa_evaluations'

    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('meetings.id'))
    question = db.Column(db.Text)
    answer = db.Column(db.Text)
    question_topic = db.Column(db.String(200))
    question_difficulty = db.Column(db.String(20))  # easy, medium, hard
    answer_score = db.Column(db.Float)  # 0-10
    answer_quality = db.Column(db.String(20))  # excellent, good, average, poor
    is_correct = db.Column(db.Boolean)
    expected_answer = db.Column(db.Text)
    ai_feedback = db.Column(db.Text)
    technical_accuracy = db.Column(db.Float)
    communication_score = db.Column(db.Float)
    depth_score = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Feedback(db.Model):
    __tablename__ = 'feedbacks'

    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('meetings.id'))
    participant_id = db.Column(db.Integer, db.ForeignKey('participants.id'))
    overall_score = db.Column(db.Float)  # 0-100
    technical_score = db.Column(db.Float)
    communication_score = db.Column(db.Float)
    confidence_score = db.Column(db.Float)
    honesty_score = db.Column(db.Float)
    knowledge_depth = db.Column(db.Float)

    # Detailed Analysis
    strengths = db.Column(db.Text)  # JSON list
    weaknesses = db.Column(db.Text)  # JSON list
    recommendations = db.Column(db.Text)  # JSON list

    # Verdict
    verdict = db.Column(db.String(20))  # hire, reject, maybe, need_more_rounds
    detailed_feedback = db.Column(db.Text)

    # Cheating Summary
    cheating_detected = db.Column(db.Boolean, default=False)
    cheating_summary = db.Column(db.Text)
    integrity_score = db.Column(db.Float)

    report_path = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
