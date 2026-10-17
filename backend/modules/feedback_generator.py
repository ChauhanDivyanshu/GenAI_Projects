# modules/feedback_generator.py
import openai
import json
from datetime import datetime
from fpdf import FPDF
from config import Config


class FeedbackGenerator:
    """
    Complete interview feedback generate karo:
    1. Overall Score
    2. Category-wise scores
    3. Strengths & Weaknesses
    4. Hire/Reject recommendation
    5. Detailed PDF report
    """

    def __init__(self):
        self.openai_client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)

    def generate_complete_feedback(self, transcript, qa_evaluations,
                                     cheating_summary, meeting_notes,
                                     candidate_name="Candidate"):
        """
        Pura feedback generate karo
        """
        feedback = {
            'candidate_name': candidate_name,
            'generated_at': datetime.now().isoformat(),
            'meeting_duration': transcript.get('duration', 0)
        }

        # 1. AI se comprehensive feedback
        ai_feedback = self._get_ai_feedback(
            transcript, qa_evaluations, cheating_summary
        )
        feedback.update(ai_feedback)

        # 2. Score calculation
        feedback['scores'] = self._calculate_scores(
            qa_evaluations, cheating_summary, ai_feedback
        )

        # 3. Verdict
        feedback['verdict'] = self._determine_verdict(feedback['scores'])

        # 4. Improvement suggestions
        feedback['improvements'] = self._get_improvements(
            qa_evaluations, ai_feedback
        )

        # 5. Comparative analysis
        feedback['comparative'] = self._comparative_analysis(feedback['scores'])

        return feedback

    def _get_ai_feedback(self, transcript, qa_evaluations, cheating_summary):
        """AI se detailed feedback lo"""

        # Prepare context
        qa_text = ""
        for i, qa in enumerate(qa_evaluations.get('evaluations', [])[:10]):
            qa_text += f"\nQ{i+1}: {qa.get('question', 'N/A')[:200]}"
            qa_text += f"\nA{i+1}: {qa.get('answer', 'N/A')[:200]}"
            qa_text += f"\nScore: {qa.get('final_scores', {}).get('weighted_average', 'N/A')}/10\n"

        cheating_text = json.dumps(cheating_summary, indent=2, default=str)[:1000]

        prompt = f"""
        Generate a comprehensive interview feedback report.

        TRANSCRIPT SUMMARY:
        {transcript.get('full_text', '')[:3000]}

        Q&A EVALUATIONS:
        {qa_text}

        Overall Q&A Stats:
        - Total Questions: {qa_evaluations.get('total_questions', 0)}
        - Correct Answers: {qa_evaluations.get('correct_answers', 0)}
        - Average Score: {qa_evaluations.get('average_score', 0)}/10

        INTEGRITY/CHEATING REPORT:
        {cheating_text}

        Generate feedback in JSON format with:

        1. "overall_assessment": Detailed overall assessment (3-5 sentences)
        2. "technical_assessment": Technical skills assessment
        3. "communication_assessment": Communication skills assessment
        4. "personality_assessment": Personality and attitude assessment
        5. "strengths": List of top 5 strengths
        6. "weaknesses": List of areas needing improvement
        7. "red_flags": Any red flags observed
        8. "positive_indicators": Positive signs
        9. "recommendation": "strongly_hire" / "hire" / "maybe" / "reject" / "strongly_reject"
        10. "recommendation_reason": Why this recommendation
        11. "suggested_role_level": "junior" / "mid" / "senior" / "lead"
        12. "topics_strong_in": Topics where candidate showed strength
        13. "topics_weak_in": Topics where candidate was weak
        14. "follow_up_questions": Questions to ask in next round (if applicable)
        15. "salary_range_suggestion": Based on demonstrated skills
        16. "hindi_feedback": Complete feedback in Hindi
        17. "one_line_verdict": One line verdict

        Be honest, detailed, and constructive.
        """

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert HR interviewer generating detailed, fair, and constructive feedback reports. Always respond in valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            print(f"Error generating AI feedback: {e}")
            return {
                'overall_assessment': 'AI feedback generation failed. Manual review needed.',
                'recommendation': 'manual_review_needed'
            }

    def _calculate_scores(self, qa_evaluations, cheating_summary, ai_feedback):
        """All scores calculate karo"""

        # Q&A based scores
        avg_qa_score = qa_evaluations.get('average_score', 5)
        accuracy = qa_evaluations.get('accuracy', 50)

        # Integrity score
        integrity = cheating_summary.get('integrity_score', 100)

        scores = {
            # Main Scores (out of 100)
            'technical_score': min(100, avg_qa_score * 10),
            'communication_score': self._estimate_communication_score(qa_evaluations),
            'confidence_score': self._estimate_confidence_score(qa_evaluations),
            'knowledge_depth': min(100, avg_qa_score * 9),
            'problem_solving': min(100, accuracy),
            'integrity_score': integrity,

            # Derived scores
            'accuracy_percentage': accuracy,
            'questions_answered_correctly': qa_evaluations.get('correct_answers', 0),
            'total_questions': qa_evaluations.get('total_questions', 0),
        }

        # Overall score (weighted)
        overall = (
            scores['technical_score'] * 0.30 +
            scores['communication_score'] * 0.15 +
            scores['confidence_score'] * 0.10 +
            scores['knowledge_depth'] * 0.20 +
            scores['problem_solving'] * 0.15 +
            scores['integrity_score'] * 0.10
        )

        scores['overall_score'] = round(overall, 1)
        scores['grade'] = self._get_grade(overall)
        scores['percentile'] = self._estimate_percentile(overall)

        return scores

    def _estimate_communication_score(self, qa_evaluations):
        """Communication score estimate"""
        scores = []
        for e in qa_evaluations.get('evaluations', []):
            comm_score = e.get('communication', e.get('final_scores', {}).get('communication', 5))
            scores.append(comm_score if isinstance(comm_score, (int, float)) else 5)

        return min(100, (sum(scores) / max(len(scores), 1)) * 10)

    def _estimate_confidence_score(self, qa_evaluations):
        """Confidence score estimate"""
        scores = []
        for e in qa_evaluations.get('evaluations', []):
            conf = e.get('confidence', e.get('final_scores', {}).get('confidence', 5))
            scores.append(conf if isinstance(conf, (int, float)) else 5)

        return min(100, (sum(scores) / max(len(scores), 1)) * 10)

    def _determine_verdict(self, scores):
        """Final verdict decide karo"""
        overall = scores['overall_score']
        integrity = scores['integrity_score']

        # Integrity check first
        if integrity < 40:
            return {
                'decision': 'REJECT',
                'reason': '🚫 Integrity score bahut low hai. Cheating detected.',
                'color': 'red',
                'emoji': '❌',
                'confidence': 'high'
            }

        if overall >= 85 and integrity >= 80:
            return {
                'decision': 'STRONGLY HIRE',
                'reason': '🌟 Excellent candidate! Outstanding performance across all areas.',
                'color': 'green',
                'emoji': '🌟',
                'confidence': 'high'
            }
        elif overall >= 70 and integrity >= 70:
            return {
                'decision': 'HIRE',
                'reason': '✅ Good candidate. Strong performance with minor areas for improvement.',
                'color': 'green',
                'emoji': '✅',
                'confidence': 'high'
            }
        elif overall >= 55 and integrity >= 60:
            return {
                'decision': 'MAYBE - NEXT ROUND',
                'reason': '🤔 Average performance. Another round recommended.',
                'color': 'yellow',
                'emoji': '🤔',
                'confidence': 'medium'
            }
        elif overall >= 40:
            return {
                'decision': 'WEAK - CONDITIONAL',
                'reason': '⚠️ Below average. Significant improvement needed.',
                'color': 'orange',
                'emoji': '⚠️',
                'confidence': 'medium'
            }
        else:
            return {
                'decision': 'REJECT',
                'reason': '❌ Poor performance. Does not meet requirements.',
                'color': 'red',
                'emoji': '❌',
                'confidence': 'high'
            }

    def _get_improvements(self, qa_evaluations, ai_feedback):
        """Improvement suggestions"""
        improvements = ai_feedback.get('weaknesses', [])

        # Add specific improvements based on weak Q&A
        for e in qa_evaluations.get('evaluations', []):
            if e.get('final_scores', {}).get('weighted_average', 5) < 5:
                topic = e.get('topic', 'General')
                improvements.append(f"Improve knowledge in: {topic}")

        return list(set(improvements))[:10]

    def _comparative_analysis(self, scores):
        """Score comparison visualization data"""
        categories = [
            'Technical', 'Communication', 'Confidence',
            'Knowledge Depth', 'Problem Solving', 'Integrity'
        ]

        candidate_scores = [
            scores['technical_score'],
            scores['communication_score'],
            scores['confidence_score'],
            scores['knowledge_depth'],
            scores['problem_solving'],
            scores['integrity_score']
        ]

        # Average benchmark (hypothetical)
        benchmark = [65, 60, 55, 60, 55, 90]

        return {
            'categories': categories,
            'candidate_scores': candidate_scores,
            'benchmark_scores': benchmark,
            'above_benchmark': sum(1 for c, b in zip(candidate_scores, benchmark) if c >= b),
            'below_benchmark': sum(1 for c, b in zip(candidate_scores, benchmark) if c < b)
        }

    def _get_grade(self, score):
        if score >= 90: return 'A+'
        if score >= 80: return 'A'
        if score >= 70: return 'B+'
        if score >= 60: return 'B'
        if score >= 50: return 'C'
        if score >= 40: return 'D'
        return 'F'

    def _estimate_percentile(self, score):
        """Estimated percentile"""
        if score >= 90: return 95
        if score >= 80: return 85
        if score >= 70: return 70
        if score >= 60: return 55
        if score >= 50: return 40
        if score >= 40: return 25
        return 10

    def generate_pdf_report(self, feedback, output_path='report.pdf'):
        """PDF report generate karo"""
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)

        # Page 1: Cover
        pdf.add_page()
        pdf.set_font('Arial', 'B', 24)
        pdf.cell(0, 20, 'Interview Assessment Report', 0, 1, 'C')
        pdf.set_font('Arial', '', 14)
        pdf.cell(0, 10, f"Candidate: {feedback.get('candidate_name', 'N/A')}", 0, 1, 'C')
        pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", 0, 1, 'C')

        # Verdict box
        verdict = feedback.get('verdict', {})
        pdf.ln(10)
        pdf.set_font('Arial', 'B', 18)
        pdf.set_fill_color(200, 255, 200) if verdict.get('decision') in ['HIRE', 'STRONGLY HIRE'] else pdf.set_fill_color(255, 200, 200)
        pdf.cell(0, 15, f"Verdict: {verdict.get('decision', 'N/A')}", 1, 1, 'C', True)

        # Overall Score
        scores = feedback.get('scores', {})
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, f"Overall Score: {scores.get('overall_score', 0)}/100 (Grade: {scores.get('grade', 'N/A')})", 0, 1, 'C')

        # Page 2: Detailed Scores
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, 'Detailed Scores', 0, 1)
        pdf.ln(5)

        score_items = [
            ('Technical Skills', scores.get('technical_score', 0)),
            ('Communication', scores.get('communication_score', 0)),
            ('Confidence', scores.get('confidence_score', 0)),
            ('Knowledge Depth', scores.get('knowledge_depth', 0)),
            ('Problem Solving', scores.get('problem_solving', 0)),
            ('Integrity', scores.get('integrity_score', 0)),
        ]

        pdf.set_font('Arial', '', 12)
        for label, score in score_items:
            # Score bar
            pdf.cell(60, 8, label, 0, 0)
            pdf.cell(20, 8, f'{score:.0f}/100', 0, 0)

            # Visual bar
            bar_width = score * 0.8
            if score >= 70:
                pdf.set_fill_color(0, 200, 0)
            elif score >= 50:
                pdf.set_fill_color(255, 165, 0)
            else:
                pdf.set_fill_color(255, 0, 0)
            pdf.cell(bar_width, 8, '', 1, 1, '', True)

        # Page 3: Strengths & Weaknesses
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, 'Strengths', 0, 1)
        pdf.set_font('Arial', '', 11)
        for s in feedback.get('strengths', []):
            pdf.cell(0, 7, f'  + {s}', 0, 1)

        pdf.ln(5)
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, 'Areas for Improvement', 0, 1)
        pdf.set_font('Arial', '', 11)
        for w in feedback.get('improvements', []):
            pdf.cell(0, 7, f'  - {w}', 0, 1)

        # Page 4: Assessment
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, 'Overall Assessment', 0, 1)
        pdf.set_font('Arial', '', 11)
        pdf.multi_cell(0, 7, feedback.get('overall_assessment', 'N/A'))

        # Recommendation
        pdf.ln(5)
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, f"Recommendation: {verdict.get('decision', 'N/A')}", 0, 1)
        pdf.set_font('Arial', '', 11)
        pdf.multi_cell(0, 7, verdict.get('reason', 'N/A'))

        # Save
        pdf.output(output_path)
        print(f"📄 PDF Report saved: {output_path}")
        return output_path


    def _estimate_percentile(self, score):
        if score >= 90: return 95
        if score >= 80: return 85
        if score >= 70: return 70
        if score >= 60: return 55
        if score >= 50: return 40
        if score >= 40: return 25
        return 10
