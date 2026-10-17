# app.py
from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import os
import json
import uuid
from datetime import datetime
import threading

from config import Config
from models.database import db, Meeting, Transcript, CheatingEvent, Feedback, QAEvaluation
from modules.screen_recorder import ScreenRecorder
from modules.speech_to_text import SpeechToTextEngine
from modules.cheating_detector import CheatingDetector
from modules.answer_evaluator import AnswerEvaluator
from modules.meeting_notes import MeetingNotesGenerator
from modules.feedback_generator import FeedbackGenerator

# Initialize Flask
app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize Database
db.init_app(app)

# Initialize Modules
recorder = ScreenRecorder()
stt_engine = SpeechToTextEngine(model_size='medium')
cheating_detector = CheatingDetector()
answer_evaluator = AnswerEvaluator()
notes_generator = MeetingNotesGenerator()
feedback_generator = FeedbackGenerator()

# Active sessions
active_sessions = {}


# ============ WEB ROUTES ============

@app.route('/')
def index():
    """Main dashboard"""
    return render_template('index.html')


@app.route('/dashboard')
def dashboard():
    """Meeting dashboard"""
    meetings = Meeting.query.order_by(Meeting.created_at.desc()).all()
    return render_template('dashboard.html', meetings=meetings)


@app.route('/report/<meeting_id>')
def report(meeting_id):
    """Meeting report page"""
    meeting = Meeting.query.filter_by(meeting_id=meeting_id).first_or_404()
    return render_template('report.html', meeting=meeting)


# ============ API ROUTES ============

@app.route('/api/meeting/start', methods=['POST'])
def start_meeting():
    """
    Meeting recording start karo
    Body: { title, meeting_type, platform, candidate_name }
    """
    data = request.json
    meeting_id = str(uuid.uuid4())[:8]

    # Database entry
    meeting = Meeting(
        meeting_id=meeting_id,
        title=data.get('title', f'Meeting {meeting_id}'),
        meeting_type=data.get('meeting_type', 'interview'),
        platform=data.get('platform', 'google_meet'),
        status='active'
    )
    db.session.add(meeting)
    db.session.commit()

    # Start recording
    recording_result = recorder.start_recording(meeting_id)

    # Start speech-to-text (real-time)
    def on_transcript(entry):
        socketio.emit('transcript_update', entry)
    stt_engine.real_time_transcribe(callback=on_transcript)

    # Start cheating detection
    cheating_detector.start_monitoring(meeting_id)

    # Start frame analysis thread
    def analyze_frames():
        while recorder.is_recording:
            frame = recorder.get_current_frame()
            if frame is not None:
                result = cheating_detector.analyze_frame(frame)
                if result and result['cheating_detected']:
                    socketio.emit('cheating_alert', result)
            import time
            time.sleep(0.5)  # Check every 500ms

    analysis_thread = threading.Thread(target=analyze_frames)
    analysis_thread.daemon = True
    analysis_thread.start()

    # Store session
    active_sessions[meeting_id] = {
        'meeting': meeting,
        'recording': recording_result,
        'start_time': datetime.now(),
        'analysis_thread': analysis_thread
    }

    return jsonify({
        'success': True,
        'meeting_id': meeting_id,
        'message': '🎬 Meeting recording started!',
        'recording': recording_result
    })


@app.route('/api/meeting/stop', methods=['POST'])
def stop_meeting():
    """
    Meeting recording band karo aur analysis start karo
    """
    data = request.json
    meeting_id = data.get('meeting_id')

    if meeting_id not in active_sessions:
        return jsonify({'error': 'Meeting not found'}), 404

    # Stop recording
    recording_result = recorder.stop_recording()

    # Stop real-time transcription
    live_transcripts = stt_engine.stop_listening()

    # Stop cheating monitoring
    cheating_summary = cheating_detector.stop_monitoring()

    # Update database
    meeting = Meeting.query.filter_by(meeting_id=meeting_id).first()
    meeting.end_time = datetime.now()
    meeting.status = 'analyzing'
    meeting.duration_minutes = recording_result['duration'] / 60
    meeting.recording_path = recording_result['video_path']
    meeting.audio_path = recording_result['audio_path']
    db.session.commit()

    # Start async analysis
    thread = threading.Thread(
        target=_analyze_meeting,
        args=(meeting_id, recording_result, cheating_summary)
    )
    thread.start()

    return jsonify({
        'success': True,
        'meeting_id': meeting_id,
        'message': '⏹️ Meeting stopped! Analysis started...',
        'duration': recording_result['duration'],
        'cheating_summary': cheating_summary
    })


def _analyze_meeting(meeting_id, recording_result, cheating_summary):
    """Background mai meeting analyze karo"""
    with app.app_context():
        try:
            socketio.emit('analysis_status', {
                'meeting_id': meeting_id,
                'step': 'transcribing',
                'message': '🎙️ Audio transcribe ho raha hai...'
            })

            # 1. Full Transcription
            transcript = stt_engine.transcribe_audio_file(
                recording_result['audio_path']
            )

            # Speaker identification
            transcript = stt_engine.identify_speakers(transcript)

            # Save transcripts to DB
            for segment in transcript['segments']:
                t = Transcript(
                    meeting_id=Meeting.query.filter_by(meeting_id=meeting_id).first().id,
                    speaker=segment.get('speaker', 'Unknown'),
                    text=segment['text'],
                    timestamp_start=segment['start'],
                    timestamp_end=segment['end'],
                    confidence=segment.get('confidence', 0),
                    is_question=segment.get('is_question', False),
                    sentiment=segment.get('sentiment', 'neutral')
                )
                db.session.add(t)
            db.session.commit()

            socketio.emit('analysis_status', {
                'meeting_id': meeting_id,
                'step': 'extracting_qa',
                'message': '❓ Questions & Answers extract ho rahe hain...'
            })

            # 2. Extract Q&A pairs
            qa_pairs = stt_engine.extract_qa_pairs(transcript)

            socketio.emit('analysis_status', {
                'meeting_id': meeting_id,
                'step': 'evaluating_answers',
                'message': '📝 Answers evaluate ho rahe hain...'
            })

            # 3. Evaluate answers
            qa_evaluations = answer_evaluator.evaluate_all_qa(qa_pairs)

            # Save Q&A evaluations
            meeting_db = Meeting.query.filter_by(meeting_id=meeting_id).first()
            for eval_item in qa_evaluations.get('evaluations', []):
                qa = QAEvaluation(
                    meeting_id=meeting_db.id,
                    question=eval_item.get('question', ''),
                    answer=eval_item.get('answer', ''),
                    answer_score=eval_item.get('final_scores', {}).get('weighted_average', 0),
                    is_correct=eval_item.get('is_correct', False),
                    ai_feedback=json.dumps(eval_item)
                )
                db.session.add(qa)
            db.session.commit()

            socketio.emit('analysis_status', {
                'meeting_id': meeting_id,
                'step': 'generating_notes',
                'message': '📋 Meeting notes generate ho rahe hain...'
            })

            # 4. Generate meeting notes
            meeting_notes = notes_generator.generate_interview_notes(
                transcript, qa_evaluations, cheating_summary
            )

            socketio.emit('analysis_status', {
                'meeting_id': meeting_id,
                'step': 'generating_feedback',
                'message': '📊 Feedback generate ho raha hai...'
            })

            # 5. Generate complete feedback
            feedback = feedback_generator.generate_complete_feedback(
                transcript=transcript,
                qa_evaluations=qa_evaluations,
                cheating_summary=cheating_summary,
                meeting_notes=meeting_notes,
                candidate_name=meeting_db.title
            )

            # Generate PDF report
            report_path = os.path.join(
                Config.RECORDING_DIR,
                f'report_{meeting_id}.pdf'
            )
            feedback_generator.generate_pdf_report(feedback, report_path)

            # Save feedback to DB
            fb = Feedback(
                meeting_id=meeting_db.id,
                overall_score=feedback['scores']['overall_score'],
                technical_score=feedback['scores']['technical_score'],
                communication_score=feedback['scores']['communication_score'],
                confidence_score=feedback['scores']['confidence_score'],
                honesty_score=feedback['scores']['integrity_score'],
                knowledge_depth=feedback['scores']['knowledge_depth'],
                strengths=json.dumps(feedback.get('strengths', [])),
                weaknesses=json.dumps(feedback.get('weaknesses', [])),
                recommendations=json.dumps(feedback.get('improvements', [])),
                verdict=feedback['verdict']['decision'],
                detailed_feedback=json.dumps(feedback),
                cheating_detected=cheating_summary.get('total_events', 0) > 0,
                cheating_summary=json.dumps(cheating_summary),
                integrity_score=cheating_summary.get('integrity_score', 100),
                report_path=report_path
            )
            db.session.add(fb)

            # Update meeting status
            meeting_db.status = 'completed'
            db.session.commit()

            socketio.emit('analysis_complete', {
                'meeting_id': meeting_id,
                'message': '✅ Analysis complete!',
                'feedback': feedback,
                'notes': meeting_notes,
                'report_path': report_path
            })

        except Exception as e:
            print(f"❌ Analysis error: {e}")
            import traceback
            traceback.print_exc()

            socketio.emit('analysis_error', {
                'meeting_id': meeting_id,
                'error': str(e)
            })


@app.route('/api/meeting/<meeting_id>/status')
def meeting_status(meeting_id):
    """Meeting ka current status"""
    meeting = Meeting.query.filter_by(meeting_id=meeting_id).first_or_404()

    return jsonify({
        'meeting_id': meeting_id,
        'status': meeting.status,
        'title': meeting.title,
        'duration': meeting.duration_minutes,
        'start_time': meeting.start_time.isoformat() if meeting.start_time else None,
        'end_time': meeting.end_time.isoformat() if meeting.end_time else None
    })


@app.route('/api/meeting/<meeting_id>/feedback')
def get_feedback(meeting_id):
    """Meeting ka feedback"""
    meeting = Meeting.query.filter_by(meeting_id=meeting_id).first_or_404()
    feedback = Feedback.query.filter_by(meeting_id=meeting.id).first()

    if not feedback:
        return jsonify({'error': 'Feedback not generated yet'}), 404

    return jsonify({
        'meeting_id': meeting_id,
        'overall_score': feedback.overall_score,
        'technical_score': feedback.technical_score,
        'communication_score': feedback.communication_score,
        'confidence_score': feedback.confidence_score,
        'integrity_score': feedback.integrity_score,
        'verdict': feedback.verdict,
        'detailed': json.loads(feedback.detailed_feedback) if feedback.detailed_feedback else {},
        'cheating': json.loads(feedback.cheating_summary) if feedback.cheating_summary else {},
        'strengths': json.loads(feedback.strengths) if feedback.strengths else [],
        'weaknesses': json.loads(feedback.weaknesses) if feedback.weaknesses else [],
        'report_path': feedback.report_path
    })


@app.route('/api/meeting/<meeting_id>/notes')
def get_notes(meeting_id):
    """Meeting ke notes"""
    meeting = Meeting.query.filter_by(meeting_id=meeting_id).first_or_404()

    transcripts = Transcript.query.filter_by(meeting_id=meeting.id).order_by(
        Transcript.timestamp_start
    ).all()

    return jsonify({
        'meeting_id': meeting_id,
        'transcripts': [{
            'speaker': t.speaker,
            'text': t.text,
            'time': t.timestamp_start,
            'is_question': t.is_question,
            'sentiment': t.sentiment
        } for t in transcripts]
    })


@app.route('/api/meeting/<meeting_id>/report/download')
def download_report(meeting_id):
    """PDF report download karo"""
    meeting = Meeting.query.filter_by(meeting_id=meeting_id).first_or_404()
    feedback = Feedback.query.filter_by(meeting_id=meeting.id).first()

    if feedback and feedback.report_path and os.path.exists(feedback.report_path):
        return send_file(feedback.report_path, as_attachment=True)

    return jsonify({'error': 'Report not found'}), 404


@app.route('/api/cheating/tab-switch', methods=['POST'])
def report_tab_switch():
    """Browser extension se tab switch report"""
    data = request.json
    event = cheating_detector.register_tab_switch()

    socketio.emit('cheating_alert', {
        'type': 'tab_switch',
        'event': event
    })

    return jsonify({'received': True, 'event': event})


@app.route('/api/cheating/copy-paste', methods=['POST'])
def report_copy_paste():
    """Copy-paste detected"""
    data = request.json
    event = cheating_detector.register_copy_paste(
        content=data.get('content', '')
    )

    socketio.emit('cheating_alert', {
        'type': 'copy_paste',
        'event': event
    })

    return jsonify({'received': True, 'event': event})


# ============ SOCKET.IO EVENTS ============

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('connected', {'status': 'Connected to server'})


@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')


@socketio.on('frame_data')
def handle_frame(data):
    """Browser se frame receive karo for analysis"""
    import base64
    import cv2
    import numpy as np

    # Decode base64 frame
    frame_data = base64.b64decode(data['frame'])
    nparr = np.frombuffer(frame_data, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if frame is not None:
        result = cheating_detector.analyze_frame(frame)
        if result and result['cheating_detected']:
            emit('cheating_alert', result)


# ============ INITIALIZE ============

with app.app_context():
    db.create_all()
    os.makedirs(Config.RECORDING_DIR, exist_ok=True)


if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════════╗
    ║     🎯 AI Meeting Analyzer & Proctor        ║
    ║     Server starting on port 5000...          ║
    ╚══════════════════════════════════════════════╝
    """)

    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
