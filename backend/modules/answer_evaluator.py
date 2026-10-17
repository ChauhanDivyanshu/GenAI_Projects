# modules/answer_evaluator.py
import openai
import google.generativeai as genai
from sentence_transformers import SentenceTransformer
import numpy as np
import json
from config import Config


class AnswerEvaluator:
    """
    Interview answers ko evaluate karo:
    1. Technical accuracy check
    2. Communication quality
    3. Depth of knowledge
    4. Confidence level
    5. Compare with ideal answer
    """

    def __init__(self):
        # OpenAI setup
        self.openai_client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)

        # Google Gemini setup
        genai.configure(api_key=Config.GOOGLE_AI_KEY)
        self.gemini_model = genai.GenerativeModel('gemini-pro')

        # Sentence similarity model
        self.similarity_model = SentenceTransformer('all-MiniLM-L6-v2')

        # Knowledge base (common interview Q&A)
        self.knowledge_base = self._load_knowledge_base()

    def evaluate_answer(self, question, answer, topic=None, difficulty=None):
        """
        Ek answer ko complete evaluate karo
        """
        evaluation = {
            'question': question,
            'answer': answer,
            'topic': topic,
            'difficulty': difficulty
        }

        # 1. AI se answer evaluate karwao
        ai_evaluation = self._ai_evaluate(question, answer, topic)
        evaluation.update(ai_evaluation)

        # 2. Knowledge base se compare
        if topic:
            kb_score = self._compare_with_knowledge_base(question, answer, topic)
            evaluation['knowledge_base_score'] = kb_score

        # 3. Answer quality metrics
        quality_metrics = self._analyze_quality(answer)
        evaluation['quality_metrics'] = quality_metrics

        # 4. Calculate final scores
        evaluation['final_scores'] = self._calculate_final_scores(evaluation)

        return evaluation

    def _ai_evaluate(self, question, answer, topic=None):
        """OpenAI/Gemini se answer evaluate karwao"""

        prompt = f"""
        You are an expert technical interviewer. Evaluate the following interview answer.

        Question: {question}
        Candidate's Answer: {answer}
        Topic: {topic or 'General'}

        Please evaluate on these parameters (score 0-10 for each):

        1. **Technical Accuracy** (0-10): Is the answer technically correct?
        2. **Completeness** (0-10): Does it cover all important points?
        3. **Depth of Knowledge** (0-10): Does candidate show deep understanding?
        4. **Communication** (0-10): How well is the answer communicated?
        5. **Confidence** (0-10): Does the answer show confidence?
        6. **Practical Knowledge** (0-10): Does candidate have practical experience?

        Also provide:
        - **is_correct**: true/false - Is the core answer correct?
        - **ideal_answer**: What would be the ideal answer?
        - **missing_points**: What important points are missing?
        - **strengths**: What did the candidate do well?
        - **improvements**: Where can candidate improve?
        - **overall_verdict**: "excellent" / "good" / "average" / "below_average" / "poor"
        - **hindi_feedback**: Feedback in Hindi for the candidate

        Respond in JSON format only.
        """

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a strict but fair technical interviewer. Always respond in valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            return result

        except Exception as e:
            print(f"OpenAI error, trying Gemini: {e}")

            # Fallback to Gemini
            try:
                response = self.gemini_model.generate_content(prompt)
                result = json.loads(response.text)
                return result
            except Exception as e2:
                print(f"Gemini error too: {e2}")
                return self._basic_evaluate(question, answer)

    def _basic_evaluate(self, question, answer):
        """Basic evaluation without AI (fallback)"""
        word_count = len(answer.split())

        # Basic scoring
        if word_count < 10:
            quality = 'poor'
            score = 2
        elif word_count < 30:
            quality = 'below_average'
            score = 4
        elif word_count < 80:
            quality = 'average'
            score = 6
        elif word_count < 150:
            quality = 'good'
            score = 7
        else:
            quality = 'excellent'
            score = 8

        return {
            'technical_accuracy': score,
            'completeness': score - 1,
            'depth_of_knowledge': score - 1,
            'communication': score,
            'confidence': score,
            'practical_knowledge': score - 1,
            'is_correct': score >= 5,
            'overall_verdict': quality,
            'ideal_answer': 'AI evaluation not available',
            'missing_points': [],
            'strengths': ['Answer provided'],
            'improvements': ['More detail needed']
        }

    def _compare_with_knowledge_base(self, question, answer, topic):
        """Knowledge base se answer compare karo"""

        # Find similar questions in knowledge base
        question_embedding = self.similarity_model.encode([question])

        best_match = None
        best_score = 0

        for kb_entry in self.knowledge_base.get(topic, []):
            kb_q_embedding = self.similarity_model.encode([kb_entry['question']])
            similarity = np.dot(question_embedding[0], kb_q_embedding[0]) / (
                np.linalg.norm(question_embedding[0]) * np.linalg.norm(kb_q_embedding[0])
            )

            if similarity > best_score:
                best_score = similarity
                best_match = kb_entry

        if best_match and best_score > 0.7:
            # Compare answer with ideal answer
            answer_embedding = self.similarity_model.encode([answer])
            ideal_embedding = self.similarity_model.encode([best_match['ideal_answer']])

            answer_similarity = np.dot(answer_embedding[0], ideal_embedding[0]) / (
                np.linalg.norm(answer_embedding[0]) * np.linalg.norm(ideal_embedding[0])
            )

            return {
                'similarity_score': float(answer_similarity),
                'matched_question': best_match['question'],
                'ideal_answer': best_match['ideal_answer'],
                'key_points_covered': self._check_key_points(
                    answer, best_match.get('key_points', [])
                )
            }

        return {'similarity_score': 0, 'matched_question': None}

    def _check_key_points(self, answer, key_points):
        """Check karo kitne key points cover hue"""
        answer_lower = answer.lower()
        covered = []
        missed = []

        for point in key_points:
            if any(keyword in answer_lower for keyword in point.lower().split()):
                covered.append(point)
            else:
                missed.append(point)

        return {
            'covered': covered,
            'missed': missed,
            'coverage_percentage': len(covered) / len(key_points) * 100 if key_points else 0
        }

    def _analyze_quality(self, answer):
        """Answer ki quality analyze karo"""
        words = answer.split()
        sentences = answer.split('.')

        return {
            'word_count': len(words),
            'sentence_count': len([s for s in sentences if s.strip()]),
            'avg_sentence_length': len(words) / max(len(sentences), 1),
            'has_examples': any(w in answer.lower() for w in
                              ['example', 'for instance', 'like', 'such as', 'jaise']),
            'has_technical_terms': self._count_technical_terms(answer),
            'is_structured': self._check_structure(answer),
            'filler_words': self._count_fillers(answer),
            'confidence_indicators': self._check_confidence(answer)
        }

    def _count_technical_terms(self, answer):
        """Technical terms count karo"""
        tech_terms = [
            'algorithm', 'database', 'api', 'framework', 'architecture',
            'design pattern', 'complexity', 'scalability', 'optimization',
            'data structure', 'OOP', 'REST', 'microservice', 'cloud',
            'docker', 'kubernetes', 'git', 'agile', 'CI/CD'
        ]
        count = sum(1 for term in tech_terms if term.lower() in answer.lower())
        return count

    def _count_fillers(self, answer):
        """Filler words count (confidence indicator)"""
        fillers = [
            'umm', 'uhh', 'basically', 'actually', 'like',
            'you know', 'sort of', 'kind of', 'I think maybe',
            'matlab', 'wo', 'basically', 'actually'
        ]
        count = sum(answer.lower().count(filler) for filler in fillers)
        return count

    def _check_confidence(self, answer):
        """Confidence level check"""
        confident_phrases = [
            'I am sure', 'definitely', 'certainly', 'I know',
            'in my experience', 'I have worked', 'I implemented',
            'mujhe pata hai', 'maine kiya hai', 'bilkul'
        ]
        uncertain_phrases = [
            'I think', 'maybe', 'I am not sure', 'probably',
            'I guess', 'might be', 'shayad', 'ho sakta hai',
            'pata nahi', 'I don\'t know'
        ]

        confident_count = sum(1 for p in confident_phrases if p.lower() in answer.lower())
        uncertain_count = sum(1 for p in uncertain_phrases if p.lower() in answer.lower())

        return {
            'confident_phrases': confident_count,
            'uncertain_phrases': uncertain_count,
            'confidence_ratio': confident_count / max(confident_count + uncertain_count, 1)
        }

    def _check_structure(self, answer):
        """Answer structured hai ya nahi"""
        structured_indicators = [
            'first', 'second', 'third', 'finally',
            'firstly', 'secondly', 'moreover', 'additionally',
            'pehle', 'doosra', 'teesra', 'iske alawa',
            '1.', '2.', '3.', '-', '•'
        ]
        return any(ind in answer.lower() for ind in structured_indicators)

    def _calculate_final_scores(self, evaluation):
        """Final scores calculate karo"""
        scores = {
            'technical': evaluation.get('technical_accuracy', 5),
            'communication': evaluation.get('communication', 5),
            'depth': evaluation.get('depth_of_knowledge', 5),
            'confidence': evaluation.get('confidence', 5),
            'completeness': evaluation.get('completeness', 5),
            'practical': evaluation.get('practical_knowledge', 5)
        }

        # Weighted average
        weights = {
            'technical': 0.3,
            'communication': 0.15,
            'depth': 0.2,
            'confidence': 0.1,
            'completeness': 0.15,
            'practical': 0.1
        }

        weighted_score = sum(
            scores[k] * weights[k] for k in scores
        )

        # Convert to percentage
        percentage = (weighted_score / 10) * 100

        scores['weighted_average'] = round(weighted_score, 2)
        scores['percentage'] = round(percentage, 1)
        scores['grade'] = self._get_grade(percentage)

        return scores

    def _get_grade(self, percentage):
        if percentage >= 90: return 'A+'
        if percentage >= 80: return 'A'
        if percentage >= 70: return 'B+'
        if percentage >= 60: return 'B'
        if percentage >= 50: return 'C'
        if percentage >= 40: return 'D'
        return 'F'

    def _load_knowledge_base(self):
        """Interview questions ka knowledge base"""
        return {
            'python': [
                {
                    'question': 'What is a decorator in Python?',
                    'ideal_answer': 'A decorator is a function that takes another function as argument and extends its behavior without modifying it. It uses @symbol syntax. Common use cases include logging, authentication, timing, etc.',
                    'key_points': ['function that wraps another function', '@syntax', 'extends behavior', 'without modification']
                },
                {
                    'question': 'What is the difference between list and tuple?',
                    'ideal_answer': 'List is mutable (can be changed), uses square brackets [], and is slower. Tuple is immutable (cannot be changed), uses parentheses (), and is faster. Tuples can be used as dictionary keys.',
                    'key_points': ['mutable vs immutable', 'square brackets vs parentheses', 'performance', 'dictionary keys']
                }
            ],
            'javascript': [
                {
                    'question': 'What is closure in JavaScript?',
                    'ideal_answer': 'A closure is a function that has access to variables in its outer scope even after the outer function has returned. It creates a persistent scope.',
                    'key_points': ['function with access to outer scope', 'persists after outer function returns', 'lexical scoping']
                }
            ],
            'data_structures': [
                {
                    'question': 'What is the difference between array and linked list?',
                    'ideal_answer': 'Array has contiguous memory, O(1) access, fixed size. Linked list has non-contiguous memory, O(n) access, dynamic size, better insertion/deletion.',
                    'key_points': ['contiguous vs non-contiguous memory', 'access time', 'insertion deletion', 'size flexibility']
                }
            ]
        }

    def evaluate_all_qa(self, qa_pairs, topic=None):
        """Saare Q&A pairs evaluate karo"""
        evaluations = []

        for i, qa in enumerate(qa_pairs):
            print(f"📝 Evaluating Q{i+1}: {qa['question'][:50]}...")

            eval_result = self.evaluate_answer(
                question=qa['question'],
                answer=qa['answer'],
                topic=topic
            )

            evaluations.append(eval_result)

        # Overall summary
        if evaluations:
            avg_score = np.mean([
                e.get('final_scores', {}).get('weighted_average', 5)
                for e in evaluations
            ])

            correct_count = sum(
                1 for e in evaluations
                if e.get('is_correct', False)
            )

            return {
                'evaluations': evaluations,
                'total_questions': len(evaluations),
                'correct_answers': correct_count,
                'accuracy': correct_count / len(evaluations) * 100,
                'average_score': round(avg_score, 2),
                'average_percentage': round((avg_score / 10) * 100, 1)
            }

        return {'evaluations': [], 'total_questions': 0}
