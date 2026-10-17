# modules/speech_to_text.py
import whisper
import speech_recognition as sr
import threading
import json
import time
from datetime import datetime
import os
import numpy as np
from pydub import AudioSegment


class SpeechToTextEngine:
    """Audio ko text mai convert karo with speaker identification"""

    def __init__(self, model_size='medium'):
        print(f"🔄 Loading Whisper model: {model_size}")
        self.model = whisper.load_model(model_size)
        self.recognizer = sr.Recognizer()
        self.is_listening = False
        self.transcripts = []
        self.real_time_text = ""
        print("✅ Whisper model loaded!")

    def transcribe_audio_file(self, audio_path):
        """
        Puri audio file ko transcribe karo
        Returns: Complete transcript with timestamps
        """
        print(f"🎙️ Transcribing: {audio_path}")

        # Whisper se transcribe
        result = self.model.transcribe(
            audio_path,
            language='hi',  # Hindi + English support
            task='transcribe',
            verbose=True,
            word_timestamps=True,
            fp16=False  # CPU ke liye
        )

        segments = []
        for segment in result['segments']:
            seg_data = {
                'id': segment['id'],
                'start': segment['start'],
                'end': segment['end'],
                'text': segment['text'].strip(),
                'confidence': segment.get('avg_logprob', 0),
                'words': []
            }

            # Word-level timestamps
            if 'words' in segment:
                for word in segment['words']:
                    seg_data['words'].append({
                        'word': word['word'],
                        'start': word['start'],
                        'end': word['end'],
                        'confidence': word.get('probability', 0)
                    })

            # Question detection
            seg_data['is_question'] = self._is_question(segment['text'])

            # Sentiment analysis
            seg_data['sentiment'] = self._analyze_sentiment(segment['text'])

            segments.append(seg_data)

        transcript = {
            'full_text': result['text'],
            'language': result['language'],
            'segments': segments,
            'duration': segments[-1]['end'] if segments else 0,
            'total_segments': len(segments),
            'transcribed_at': datetime.now().isoformat()
        }

        print(f"✅ Transcription complete: {len(segments)} segments")
        return transcript

    def real_time_transcribe(self, callback=None):
        """
        Real-time microphone se transcribe karo
        Jab meeting chal rhi ho tab live text dikhe
        """
        self.is_listening = True

        def listen_loop():
            with sr.Microphone() as source:
                print("🎤 Real-time listening started...")
                self.recognizer.adjust_for_ambient_noise(source, duration=2)

                while self.is_listening:
                    try:
                        audio = self.recognizer.listen(
                            source, timeout=5, phrase_time_limit=30
                        )

                        # Google Speech Recognition (fast, real-time ke liye)
                        try:
                            text = self.recognizer.recognize_google(
                                audio, language='hi-IN'
                            )
                        except:
                            text = self.recognizer.recognize_google(
                                audio, language='en-IN'
                            )

                        timestamp = time.time()

                        entry = {
                            'text': text,
                            'timestamp': timestamp,
                            'time_str': datetime.now().strftime('%H:%M:%S'),
                            'is_question': self._is_question(text),
                            'sentiment': self._analyze_sentiment(text)
                        }

                        self.transcripts.append(entry)
                        self.real_time_text += f"\n[{entry['time_str']}] {text}"

                        # Callback for real-time updates
                        if callback:
                            callback(entry)

                        print(f"📝 [{entry['time_str']}]: {text}")

                    except sr.WaitTimeoutError:
                        continue
                    except sr.UnknownValueError:
                        continue
                    except Exception as e:
                        print(f"❌ Error: {e}")
                        continue

        self.listen_thread = threading.Thread(target=listen_loop)
        self.listen_thread.daemon = True
        self.listen_thread.start()

    def stop_listening(self):
        """Real-time listening band karo"""
        self.is_listening = False
        return self.transcripts

    def identify_speakers(self, transcript):
        """
        Speaker diarization - kaun bol rha h identify karo
        Simple approach: based on audio characteristics
        """
        speakers = {}
        current_speaker = "Speaker 1"
        speaker_count = 1

        for segment in transcript['segments']:
            # Check for pause (speaker change indicator)
            if segment.get('pause_before', 0) > 2.0:
                speaker_count += 1
                current_speaker = f"Speaker {speaker_count}"

            segment['speaker'] = current_speaker

            if current_speaker not in speakers:
                speakers[current_speaker] = {
                    'total_time': 0,
                    'total_words': 0,
                    'segments': 0
                }

            speakers[current_speaker]['total_time'] += (segment['end'] - segment['start'])
            speakers[current_speaker]['total_words'] += len(segment['text'].split())
            speakers[current_speaker]['segments'] += 1

        transcript['speakers'] = speakers
        return transcript

    def extract_qa_pairs(self, transcript):
        """
        Questions aur answers identify karo
        Interview ke liye bahut important
        """
        qa_pairs = []
        current_question = None

        for i, segment in enumerate(transcript['segments']):
            if segment['is_question']:
                if current_question and i > 0:
                    # Previous question ka answer collect karo
                    answer_texts = []
                    for j in range(current_question['index'] + 1, i):
                        if not transcript['segments'][j]['is_question']:
                            answer_texts.append(transcript['segments'][j]['text'])

                    if answer_texts:
                        qa_pairs.append({
                            'question': current_question['text'],
                            'question_time': current_question['timestamp'],
                            'answer': ' '.join(answer_texts),
                            'answer_duration': segment['start'] - current_question['timestamp']
                        })

                current_question = {
                    'text': segment['text'],
                    'timestamp': segment['start'],
                    'index': i
                }

        # Last question ka answer
        if current_question:
            answer_texts = []
            for j in range(current_question['index'] + 1, len(transcript['segments'])):
                if not transcript['segments'][j]['is_question']:
                    answer_texts.append(transcript['segments'][j]['text'])

            if answer_texts:
                qa_pairs.append({
                    'question': current_question['text'],
                    'question_time': current_question['timestamp'],
                    'answer': ' '.join(answer_texts)
                })

        return qa_pairs

    def _is_question(self, text):
        """Check karo ye question hai ya nahi"""
        question_indicators = [
            '?', 'what', 'how', 'why', 'when', 'where', 'which', 'who',
            'kya', 'kaise', 'kyun', 'kab', 'kahan', 'kaun', 'konsa',
            'can you', 'could you', 'tell me', 'explain', 'describe',
            'batao', 'samjhao', 'define', 'difference between',
            'क्या', 'कैसे', 'क्यों', 'कब', 'कहाँ'
        ]

        text_lower = text.lower().strip()
        return any(indicator in text_lower for indicator in question_indicators)

    def _analyze_sentiment(self, text):
        """Basic sentiment analysis"""
        positive_words = [
            'good', 'great', 'excellent', 'perfect', 'right', 'correct',
            'achha', 'badhiya', 'sahi', 'theek', 'yes', 'haan',
            'amazing', 'wonderful', 'impressive', 'exactly'
        ]
        negative_words = [
            'wrong', 'bad', 'incorrect', 'no', 'not', 'galat',
            'nahi', 'problem', 'issue', 'difficult', 'fail',
            'poor', 'weak', 'missing'
        ]

        text_lower = text.lower()
        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)

        if pos_count > neg_count:
            return 'positive'
        elif neg_count > pos_count:
            return 'negative'
        return 'neutral'
