# modules/meeting_notes.py
import openai
import google.generativeai as genai
from datetime import datetime
import json
from config import Config


class MeetingNotesGenerator:
    """
    Meeting ke notes auto-generate karo:
    1. Key Points
    2. Summary
    3. Action Items
    4. Questions Asked
    5. Decisions Made
    6. Topics Discussed
    """

    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)
        genai.configure(api_key=Config.GOOGLE_AI_KEY)
        self.gemini_model = genai.GenerativeModel('gemini-pro')

    def generate_notes(self, transcript, meeting_type='interview'):
        """
        Complete meeting notes generate karo
        """
        full_text = transcript.get('full_text', '')
        segments = transcript.get('segments', [])

        if not full_text:
            return {'error': 'No transcript available'}

        # AI se notes generate karwao
        notes = self._ai_generate_notes(full_text, meeting_type)

        # Timeline with key moments
        notes['timeline'] = self._create_timeline(segments)

        # Word cloud data
        notes['word_frequency'] = self._get_word_frequency(full_text)

        # Speaker stats
        notes['speaker_stats'] = self._get_speaker_stats(segments)

        notes['generated_at'] = datetime.now().isoformat()
        notes['meeting_type'] = meeting_type

        return notes

    def _ai_generate_notes(self, transcript_text, meeting_type):
        """AI se structured notes banwao"""

        prompt = f"""
        Analyze this {meeting_type} transcript and generate comprehensive notes.

        Transcript:
        {transcript_text[:8000]}

        Generate the following in JSON format:

        1. **summary**: A brief 3-5 sentence summary of the entire {meeting_type}
        2. **key_points**: List of most important points discussed (max 10)
        3. **topics_discussed**: List of topics/subjects covered with brief description
        4. **questions_asked**: All questions that were asked (with approximate context)
        5. **answers_given**: Key answers/responses provided
        6. **action_items**: Any action items or follow-ups mentioned
        7. **decisions_made**: Any decisions taken during the meeting
        8. **important_quotes**: Notable statements or quotes
        9. **technical_terms**: Technical terms used with brief explanations
        10. **mood_analysis**: Overall mood/tone of the meeting (formal, casual, tense, friendly)

        {"11. **interview_specific**: For interviews, include:" if meeting_type == 'interview' else ""}
        {"    - candidate_performance_summary" if meeting_type == 'interview' else ""}
        {"    - topics_tested" if meeting_type == 'interview' else ""}
        {"    - strong_areas" if meeting_type == 'interview' else ""}
        {"    - weak_areas" if meeting_type == 'interview' else ""}
        {"    - overall_impression" if meeting_type == 'interview' else ""}

        Also provide:
        - **hindi_summary**: Summary in Hindi
        - **one_line_summary**: One line summary

        Respond in valid JSON only.
        """

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert meeting notes taker. Generate structured, comprehensive notes. Always respond in valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            print(f"OpenAI error, trying Gemini: {e}")
            try:
                response = self.gemini_model.generate_content(prompt)
                # Clean and parse response
                text = response.text
                if '```json' in text:
                    text = text.split('```json')[1].split('```')[0]
                return json.loads(text)
            except Exception as e2:
                print(f"Gemini error: {e2}")
                return self._basic_notes(transcript_text)

    def _basic_notes(self, text):
        """Basic notes without AI"""
        sentences = text.split('.')

        return {
            'summary': '. '.join(sentences[:5]) + '.',
            'key_points': sentences[:10],
            'topics_discussed': ['Meeting content'],
            'questions_asked': [s.strip() for s in sentences if '?' in s],
            'one_line_summary': sentences[0] if sentences else 'No content',
            'word_count': len(text.split()),
            'duration_estimate': f"{len(text.split()) // 150} minutes"
        }

    def _create_timeline(self, segments):
        """Meeting ki timeline banao"""
        timeline = []

        for segment in segments:
            entry = {
                'time': f"{segment['start']:.1f}s",
                'time_formatted': self._format_time(segment['start']),
                'speaker': segment.get('speaker', 'Unknown'),
                'text': segment['text'][:100],
                'is_question': segment.get('is_question', False),
                'sentiment': segment.get('sentiment', 'neutral')
            }

            # Mark important moments
            if segment.get('is_question'):
                entry['marker'] = '❓ Question'
            elif segment.get('sentiment') == 'positive':
                entry['marker'] = '✅ Positive'
            elif segment.get('sentiment') == 'negative':
                entry['marker'] = '❌ Negative'

            timeline.append(entry)

        return timeline

    def _format_time(self, seconds):
        """Seconds ko HH:MM:SS mai convert"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _get_word_frequency(self, text):
        """Important words ki frequency"""
        stop_words = set([
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'can', 'shall',
            'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
            'it', 'this', 'that', 'these', 'those', 'i', 'you', 'he',
            'she', 'we', 'they', 'me', 'him', 'her', 'us', 'them',
            'and', 'but', 'or', 'so', 'if', 'then', 'than', 'not',
            'hai', 'ho', 'hain', 'tha', 'thi', 'the', 'ka', 'ki',
            'ke', 'ko', 'se', 'mai', 'par', 'ye', 'wo', 'aur', 'ya'
        ])

        words = text.lower().split()
        word_freq = {}

        for word in words:
            word = word.strip('.,!?;:()[]{}"\'-')
            if word and word not in stop_words and len(word) > 2:
                word_freq[word] = word_freq.get(word, 0) + 1

        # Sort by frequency
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_words[:50])

    def _get_speaker_stats(self, segments):
        """Speaker statistics"""
        stats = {}

        for segment in segments:
            speaker = segment.get('speaker', 'Unknown')

            if speaker not in stats:
                stats[speaker] = {
                    'total_time': 0,
                    'word_count': 0,
                    'segments': 0,
                    'questions_asked': 0,
                    'avg_segment_length': 0
                }

            duration = segment['end'] - segment['start']
            words = len(segment['text'].split())

            stats[speaker]['total_time'] += duration
            stats[speaker]['word_count'] += words
            stats[speaker]['segments'] += 1

            if segment.get('is_question'):
                stats[speaker]['questions_asked'] += 1

        # Calculate averages
        for speaker in stats:
            if stats[speaker]['segments'] > 0:
                stats[speaker]['avg_segment_length'] = round(
                    stats[speaker]['total_time'] / stats[speaker]['segments'], 1
                )
                stats[speaker]['total_time'] = round(stats[speaker]['total_time'], 1)

        return stats

    def generate_interview_notes(self, transcript, qa_evaluations, cheating_summary):
        """
        Interview specific detailed notes
        """
        notes = self.generate_notes(transcript, 'interview')

        # Add interview-specific sections
        notes['qa_summary'] = {
            'total_questions': len(qa_evaluations.get('evaluations', [])),
            'correct_answers': qa_evaluations.get('correct_answers', 0),
            'accuracy': qa_evaluations.get('accuracy', 0),
            'avg_score': qa_evaluations.get('average_score', 0),
            'question_topics': [
                e.get('topic', 'General')
                for e in qa_evaluations.get('evaluations', [])
            ]
        }

        notes['integrity_report'] = {
            'cheating_detected': cheating_summary.get('cheating_detected', False),
            'integrity_score': cheating_summary.get('integrity_score', 100),
            'risk_level': cheating_summary.get('risk_level', 'clean'),
            'events_count': cheating_summary.get('total_events', 0)
        }

        return notes
