# modules/cheating_detector.py
import cv2
import mediapipe as mp
import numpy as np
import time
from datetime import datetime
import threading
from collections import deque


class CheatingDetector:
    """
    Interview mai cheating detect karo:
    1. 👁️ Eye tracking - kahi aur dekh rha h
    2. 📱 Phone detection
    3. 👥 Multiple faces - koi help kr rha h
    4. 🖥️ Tab switching
    5. 😶 Face absent
    6. 🎤 Voice change detection
    7. 📋 Reading from screen (eye pattern)
    """

    def __init__(self):
        # MediaPipe Face Mesh
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=5,  # Multiple faces detect
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        # MediaPipe Face Detection
        self.mp_face_detection = mp.solutions.face_detection
        self.face_detection = self.mp_face_detection.FaceDetection(
            min_detection_confidence=0.5
        )

        # Object Detection for phone
        self.mp_objectron = mp.solutions.objectron

        # Cheating events log
        self.cheating_events = []
        self.is_monitoring = False

        # Thresholds
        self.EYE_AWAY_TIME = 3.0  # 3 seconds se zyada aur dekhe to suspicious
        self.FACE_ABSENT_TIME = 5.0
        self.TAB_SWITCH_LIMIT = 3

        # Tracking variables
        self.eye_away_start = None
        self.face_absent_start = None
        self.tab_switches = 0
        self.last_face_count = 1

        # History for pattern analysis
        self.eye_positions = deque(maxlen=300)  # Last 10 seconds at 30fps
        self.face_presence = deque(maxlen=300)
        self.gaze_directions = deque(maxlen=300)

    def start_monitoring(self, meeting_id):
        """Cheating monitoring start karo"""
        self.meeting_id = meeting_id
        self.is_monitoring = True
        self.monitoring_start = time.time()
        self.cheating_events = []

        print(f"🔍 Cheating monitoring started for meeting: {meeting_id}")

    def analyze_frame(self, frame, timestamp=None):
        """
        Har frame ko analyze karo for cheating
        Returns: dict of detected cheating indicators
        """
        if not self.is_monitoring:
            return None

        if timestamp is None:
            timestamp = time.time() - self.monitoring_start

        results = {
            'timestamp': timestamp,
            'cheating_detected': False,
            'events': [],
            'risk_level': 'low'
        }

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # 1. Face Detection & Count
        face_results = self._detect_faces(rgb_frame, timestamp)
        results['events'].extend(face_results)

        # 2. Eye Tracking & Gaze
        eye_results = self._track_eyes(rgb_frame, timestamp)
        results['events'].extend(eye_results)

        # 3. Head Pose Estimation
        head_results = self._estimate_head_pose(rgb_frame, timestamp)
        results['events'].extend(head_results)

        # 4. Phone Detection
        phone_results = self._detect_phone(rgb_frame, timestamp)
        results['events'].extend(phone_results)

        # 5. Reading Pattern Detection
        reading_results = self._detect_reading_pattern(timestamp)
        results['events'].extend(reading_results)

        # 6. Lip Sync Check (koi aur bol rha h?)
        lip_results = self._check_lip_movement(rgb_frame, timestamp)
        results['events'].extend(lip_results)

        # Overall risk calculate
        if results['events']:
            results['cheating_detected'] = True
            severities = [e['severity'] for e in results['events']]
            if 'critical' in severities:
                results['risk_level'] = 'critical'
            elif 'high' in severities:
                results['risk_level'] = 'high'
            elif 'medium' in severities:
                results['risk_level'] = 'medium'

        return results

    def _detect_faces(self, rgb_frame, timestamp):
        """Face count check - multiple faces = someone helping"""
        events = []

        face_results = self.face_detection.process(rgb_frame)

        if face_results.detections:
            face_count = len(face_results.detections)
            self.face_presence.append((timestamp, face_count))

            # Multiple faces detected
            if face_count > 1:
                event = {
                    'type': 'multiple_faces',
                    'description': f'⚠️ {face_count} faces detected! Koi aur help kar raha hai!',
                    'severity': 'critical',
                    'timestamp': timestamp,
                    'face_count': face_count,
                    'confidence': 0.9
                }
                events.append(event)
                self.cheating_events.append(event)
                self.last_face_count = face_count

            # Face absent tha aur ab aaya
            if self.face_absent_start is not None:
                absent_duration = timestamp - self.face_absent_start
                if absent_duration > self.FACE_ABSENT_TIME:
                    event = {
                        'type': 'face_returned_after_absence',
                        'description': f'😶 Face {absent_duration:.1f} seconds ke liye absent tha!',
                        'severity': 'high',
                        'timestamp': timestamp,
                        'duration': absent_duration,
                        'confidence': 0.85
                    }
                    events.append(event)
                    self.cheating_events.append(event)
                self.face_absent_start = None
        else:
            # No face detected
            self.face_presence.append((timestamp, 0))

            if self.face_absent_start is None:
                self.face_absent_start = timestamp
            else:
                absent_duration = timestamp - self.face_absent_start
                if absent_duration > self.FACE_ABSENT_TIME:
                    event = {
                        'type': 'face_absent',
                        'description': f'😶 Face {absent_duration:.1f} seconds se dikhai nahi de raha!',
                        'severity': 'high',
                        'timestamp': timestamp,
                        'duration': absent_duration,
                        'confidence': 0.9
                    }
                    events.append(event)
                    self.cheating_events.append(event)

        return events

    def _track_eyes(self, rgb_frame, timestamp):
        """Eye tracking - kahan dekh rha h candidate"""
        events = []

        face_mesh_results = self.face_mesh.process(rgb_frame)

        if face_mesh_results.multi_face_landmarks:
            for face_landmarks in face_mesh_results.multi_face_landmarks:
                # Eye landmarks
                # Left eye: 33, 160, 158, 133, 153, 144
                # Right eye: 362, 385, 387, 263, 373, 380
                # Iris: Left 468-472, Right 473-477

                h, w = rgb_frame.shape[:2]

                # Left iris center
                left_iris = face_landmarks.landmark[468]
                left_iris_x = int(left_iris.x * w)
                left_iris_y = int(left_iris.y * h)

                # Right iris center
                right_iris = face_landmarks.landmark[473]
                right_iris_x = int(right_iris.x * w)
                right_iris_y = int(right_iris.y * h)

                # Left eye corners
                left_corner_inner = face_landmarks.landmark[133]
                left_corner_outer = face_landmarks.landmark[33]

                # Gaze direction calculate
                eye_center_x = (left_iris_x + right_iris_x) / 2
                eye_center_y = (left_iris_y + right_iris_y) / 2

                gaze_direction = self._calculate_gaze_direction(
                    face_landmarks, w, h
                )

                self.gaze_directions.append((timestamp, gaze_direction))
                self.eye_positions.append((timestamp, eye_center_x, eye_center_y))

                # Check if looking away
                if gaze_direction in ['left', 'right', 'up', 'down']:
                    if self.eye_away_start is None:
                        self.eye_away_start = timestamp
                    else:
                        away_duration = timestamp - self.eye_away_start
                        if away_duration > self.EYE_AWAY_TIME:
                            event = {
                                'type': 'eye_away',
                                'description': f'👁️ Candidate {gaze_direction} taraf {away_duration:.1f}s se dekh raha hai! Screen padhne ki possibility.',
                                'severity': 'medium' if away_duration < 5 else 'high',
                                'timestamp': timestamp,
                                'direction': gaze_direction,
                                'duration': away_duration,
                                'confidence': 0.8
                            }
                            events.append(event)
                            self.cheating_events.append(event)
                else:
                    self.eye_away_start = None

        return events

    def _calculate_gaze_direction(self, face_landmarks, w, h):
        """Gaze direction calculate karo"""
        # Nose tip
        nose = face_landmarks.landmark[1]

        # Left iris
        left_iris = face_landmarks.landmark[468]
        right_iris = face_landmarks.landmark[473]

        # Eye corners for reference
        left_outer = face_landmarks.landmark[33]
        left_inner = face_landmarks.landmark[133]
        right_inner = face_landmarks.landmark[362]
        right_outer = face_landmarks.landmark[263]

        # Calculate horizontal gaze ratio
        left_eye_width = abs(left_inner.x - left_outer.x)
        left_iris_pos = abs(left_iris.x - left_outer.x) / left_eye_width if left_eye_width > 0 else 0.5

        right_eye_width = abs(right_outer.x - right_inner.x)
        right_iris_pos = abs(right_iris.x - right_inner.x) / right_eye_width if right_eye_width > 0 else 0.5

        avg_gaze = (left_iris_pos + right_iris_pos) / 2

        # Vertical gaze
        left_upper = face_landmarks.landmark[159]
        left_lower = face_landmarks.landmark[145]
        eye_height = abs(left_upper.y - left_lower.y)
        vertical_pos = abs(left_iris.y - left_upper.y) / eye_height if eye_height > 0 else 0.5

        if avg_gaze < 0.3:
            return 'right'
        elif avg_gaze > 0.7:
            return 'left'
        elif vertical_pos < 0.3:
            return 'up'
        elif vertical_pos > 0.7:
            return 'down'
        else:
            return 'center'

    def _estimate_head_pose(self, rgb_frame, timestamp):
        """Head direction check - screen ke taraf dekh rha h ya side mai"""
        events = []

        face_mesh_results = self.face_mesh.process(rgb_frame)

        if face_mesh_results.multi_face_landmarks:
            for face_landmarks in face_mesh_results.multi_face_landmarks:
                h, w = rgb_frame.shape[:2]

                # Key facial landmarks for pose estimation
                nose_tip = face_landmarks.landmark[1]
                chin = face_landmarks.landmark[199]
                left_eye = face_landmarks.landmark[33]
                right_eye = face_landmarks.landmark[263]
                left_mouth = face_landmarks.landmark[61]
                right_mouth = face_landmarks.landmark[291]

                # Simple head turn detection
                face_center_x = (left_eye.x + right_eye.x) / 2
                nose_offset = abs(nose_tip.x - face_center_x)

                # Significant head turn
                if nose_offset > 0.05:  # Threshold
                    direction = 'left' if nose_tip.x < face_center_x else 'right'
                    event = {
                        'type': 'head_turned',
                        'description': f'🔄 Head {direction} taraf turn hai - side mai dekh raha hai',
                        'severity': 'medium',
                        'timestamp': timestamp,
                        'direction': direction,
                        'offset': float(nose_offset),
                        'confidence': 0.75
                    }
                    events.append(event)
                    self.cheating_events.append(event)

        return events

    def _detect_phone(self, rgb_frame, timestamp):
        """Phone detection - mobile use kr rha h kya"""
        events = []

        # Simple phone detection using color and shape
        # (For production, use YOLO or similar object detection)

        hsv = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2HSV)

        # Detect rectangular objects near face
        gray = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            area = cv2.contourArea(contour)
            if 5000 < area < 50000:  # Phone-sized object
                peri = cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, 0.02 * peri, True)

                if len(approx) == 4:  # Rectangle
                    x, y, w, h = cv2.boundingRect(approx)
                    aspect_ratio = h / w if w > 0 else 0

                    # Phone aspect ratio (roughly 2:1)
                    if 1.5 < aspect_ratio < 2.5:
                        event = {
                            'type': 'phone_detected',
                            'description': '📱 Phone jaisa object detect hua! Mobile se answer copy kar sakta hai.',
                            'severity': 'high',
                            'timestamp': timestamp,
                            'confidence': 0.6,
                            'bbox': [x, y, w, h]
                        }
                        events.append(event)
                        self.cheating_events.append(event)

        return events

    def _detect_reading_pattern(self, timestamp):
        """
        Reading pattern detect karo -
        Agar candidate consistently ek direction mai dekh rha h
        to wo kuch padh rha h
        """
        events = []

        if len(self.gaze_directions) < 30:  # Need at least 1 second of data
            return events

        # Last 3 seconds of gaze
        recent_gazes = list(self.gaze_directions)[-90:]

        # Count directions
        direction_counts = {}
        for _, direction in recent_gazes:
            direction_counts[direction] = direction_counts.get(direction, 0) + 1

        total = len(recent_gazes)

        # If looking at one side more than 60% of time
        for direction, count in direction_counts.items():
            if direction != 'center' and (count / total) > 0.6:
                event = {
                    'type': 'reading_pattern',
                    'description': f'📖 Candidate {direction} side mai zyada dekh raha hai ({count/total*100:.0f}% time). Screen se padh raha ho sakta hai!',
                    'severity': 'medium',
                    'timestamp': timestamp,
                    'direction': direction,
                    'percentage': count / total * 100,
                    'confidence': 0.7
                }
                events.append(event)
                self.cheating_events.append(event)

        return events

    def _check_lip_movement(self, rgb_frame, timestamp):
        """Check if lips are moving when audio is playing"""
        events = []
        # Lip movement detection using face mesh
        face_mesh_results = self.face_mesh.process(rgb_frame)

        if face_mesh_results.multi_face_landmarks:
            for face_landmarks in face_mesh_results.multi_face_landmarks:
                # Upper lip: 13, Lower lip: 14
                upper_lip = face_landmarks.landmark[13]
                lower_lip = face_landmarks.landmark[14]

                lip_distance = abs(upper_lip.y - lower_lip.y)

                # Store lip movement data
                if not hasattr(self, 'lip_movements'):
                    self.lip_movements = deque(maxlen=300)

                self.lip_movements.append((timestamp, lip_distance))

        return events

    def register_tab_switch(self, timestamp=None):
        """Tab switch event register karo (from browser extension)"""
        if timestamp is None:
            timestamp = time.time() - self.monitoring_start

        self.tab_switches += 1

        event = {
            'type': 'tab_switch',
            'description': f'🖥️ Tab switch detected! Total switches: {self.tab_switches}. Candidate doosri tab mai gaya - answer search kar sakta hai.',
            'severity': 'high' if self.tab_switches > self.TAB_SWITCH_LIMIT else 'medium',
            'timestamp': timestamp,
            'total_switches': self.tab_switches,
            'confidence': 1.0
        }

        self.cheating_events.append(event)
        return event

    def register_copy_paste(self, timestamp=None, content=''):
        """Copy-paste detect hua"""
        if timestamp is None:
            timestamp = time.time() - self.monitoring_start

        event = {
            'type': 'copy_paste',
            'description': f'📋 Copy-Paste detected! Candidate ne kuch copy kiya.',
            'severity': 'critical',
            'timestamp': timestamp,
            'content_preview': content[:100] if content else '',
            'confidence': 1.0
        }

        self.cheating_events.append(event)
        return event

    def get_cheating_summary(self):
        """Pura cheating summary do"""
        if not self.cheating_events:
            return {
                'total_events': 0,
                'risk_level': 'clean',
                'integrity_score': 100,
                'summary': '✅ Koi cheating detect nahi hui. Candidate honest lagta hai.',
                'events_by_type': {},
                'timeline': []
            }

        # Count by type
        events_by_type = {}
        for event in self.cheating_events:
            etype = event['type']
            if etype not in events_by_type:
                events_by_type[etype] = []
            events_by_type[etype].append(event)

        # Severity counts
        severity_counts = {
            'critical': 0, 'high': 0, 'medium': 0, 'low': 0
        }
        for event in self.cheating_events:
            severity_counts[event['severity']] += 1

        # Integrity score calculate
        deductions = (
            severity_counts['critical'] * 20 +
            severity_counts['high'] * 10 +
            severity_counts['medium'] * 5 +
            severity_counts['low'] * 2
        )
        integrity_score = max(0, 100 - deductions)

        # Risk level
        if integrity_score >= 80:
            risk_level = 'low'
        elif integrity_score >= 60:
            risk_level = 'medium'
        elif integrity_score >= 40:
            risk_level = 'high'
        else:
            risk_level = 'critical'

        # Summary text
        summary_parts = []
        if 'multiple_faces' in events_by_type:
            summary_parts.append(f"👥 {len(events_by_type['multiple_faces'])} baar multiple faces detect hue")
        if 'tab_switch' in events_by_type:
            summary_parts.append(f"🖥️ {len(events_by_type['tab_switch'])} tab switches hue")
        if 'eye_away' in events_by_type:
            summary_parts.append(f"👁️ {len(events_by_type['eye_away'])} baar screen se dur dekha")
        if 'phone_detected' in events_by_type:
            summary_parts.append(f"📱 {len(events_by_type['phone_detected'])} baar phone detect hua")
        if 'face_absent' in events_by_type:
            summary_parts.append(f"😶 {len(events_by_type['face_absent'])} baar face absent tha")

        return {
            'total_events': len(self.cheating_events),
            'risk_level': risk_level,
            'integrity_score': integrity_score,
            'severity_counts': severity_counts,
            'summary': ' | '.join(summary_parts) if summary_parts else 'Minor suspicious activity detected.',
            'events_by_type': {k: len(v) for k, v in events_by_type.items()},
            'detailed_events': self.cheating_events,
            'timeline': sorted(self.cheating_events, key=lambda x: x['timestamp'])
        }

    def stop_monitoring(self):
        """Monitoring band karo"""
        self.is_monitoring = False
        return self.get_cheating_summary()
