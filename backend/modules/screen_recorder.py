# modules/screen_recorder.py
import cv2
import numpy as np
import pyaudio
import wave
import threading
import time
import mss
from datetime import datetime
import os


class ScreenRecorder:
    """Google Meet screen + audio recorder"""

    def __init__(self, output_dir='static/recordings'):
        self.output_dir = output_dir
        self.is_recording = False
        self.frames = []
        self.audio_frames = []
        self.start_time = None
        self.video_writer = None
        self.audio_stream = None

        # Settings
        self.fps = 15
        self.screen_region = None  # None = full screen
        self.audio_sample_rate = 44100
        self.audio_channels = 2
        self.audio_chunk = 1024

        os.makedirs(output_dir, exist_ok=True)

    def start_recording(self, meeting_id):
        """Recording start karo"""
        self.meeting_id = meeting_id
        self.is_recording = True
        self.start_time = datetime.now()

        timestamp = self.start_time.strftime('%Y%m%d_%H%M%S')
        self.video_path = os.path.join(
            self.output_dir, f'meeting_{meeting_id}_{timestamp}.mp4'
        )
        self.audio_path = os.path.join(
            self.output_dir, f'audio_{meeting_id}_{timestamp}.wav'
        )

        # Screen recording thread
        self.screen_thread = threading.Thread(target=self._record_screen)
        self.screen_thread.daemon = True
        self.screen_thread.start()

        # Audio recording thread
        self.audio_thread = threading.Thread(target=self._record_audio)
        self.audio_thread.daemon = True
        self.audio_thread.start()

        # Webcam recording thread (for face monitoring)
        self.webcam_thread = threading.Thread(target=self._record_webcam)
        self.webcam_thread.daemon = True
        self.webcam_thread.start()

        print(f"✅ Recording started for meeting: {meeting_id}")
        return {
            'status': 'recording',
            'video_path': self.video_path,
            'audio_path': self.audio_path
        }

    def _record_screen(self):
        """Screen capture karo"""
        with mss.mss() as sct:
            # Monitor select karo
            monitor = sct.monitors[1]  # Primary monitor

            # Video writer setup
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            self.video_writer = cv2.VideoWriter(
                self.video_path, fourcc, self.fps,
                (monitor['width'], monitor['height'])
            )

            while self.is_recording:
                # Screenshot lo
                screenshot = sct.grab(monitor)
                frame = np.array(screenshot)

                # BGRA to BGR convert
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                # Timestamp overlay
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cv2.putText(frame, timestamp, (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                # Frame save
                self.video_writer.write(frame)
                self.frames.append({
                    'timestamp': time.time() - self.start_time.timestamp(),
                    'frame': frame
                })

                # FPS maintain
                time.sleep(1 / self.fps)

            self.video_writer.release()

    def _record_audio(self):
        """System + Mic audio record karo"""
        p = pyaudio.PyAudio()

        # Audio stream open
        self.audio_stream = p.open(
            format=pyaudio.paInt16,
            channels=self.audio_channels,
            rate=self.audio_sample_rate,
            input=True,
            frames_per_buffer=self.audio_chunk
        )

        while self.is_recording:
            data = self.audio_stream.read(self.audio_chunk, exception_on_overflow=False)
            self.audio_frames.append(data)

        # Audio save
        self.audio_stream.stop_stream()
        self.audio_stream.close()
        p.terminate()

        # WAV file save
        wf = wave.open(self.audio_path, 'wb')
        wf.setnchannels(self.audio_channels)
        wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(self.audio_sample_rate)
        wf.writeframes(b''.join(self.audio_frames))
        wf.close()

        print(f"✅ Audio saved: {self.audio_path}")

    def _record_webcam(self):
        """Webcam se face monitor karo"""
        self.webcam_cap = cv2.VideoCapture(0)
        self.webcam_frames = []

        webcam_path = os.path.join(
            self.output_dir,
            f'webcam_{self.meeting_id}_{self.start_time.strftime("%Y%m%d_%H%M%S")}.mp4'
        )

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        webcam_writer = cv2.VideoWriter(
            webcam_path, fourcc, 10,
            (640, 480)
        )

        while self.is_recording:
            ret, frame = self.webcam_cap.read()
            if ret:
                webcam_writer.write(frame)
                self.webcam_frames.append({
                    'timestamp': time.time() - self.start_time.timestamp(),
                    'frame': frame
                })
            time.sleep(0.1)

        webcam_writer.release()
        self.webcam_cap.release()
        self.webcam_path = webcam_path

    def stop_recording(self):
        """Recording band karo"""
        self.is_recording = False
        self.end_time = datetime.now()

        # Threads join karo
        if hasattr(self, 'screen_thread'):
            self.screen_thread.join(timeout=5)
        if hasattr(self, 'audio_thread'):
            self.audio_thread.join(timeout=5)
        if hasattr(self, 'webcam_thread'):
            self.webcam_thread.join(timeout=5)

        duration = (self.end_time - self.start_time).total_seconds()

        print(f"⏹️ Recording stopped. Duration: {duration:.1f} seconds")

        return {
            'status': 'stopped',
            'video_path': self.video_path,
            'audio_path': self.audio_path,
            'webcam_path': getattr(self, 'webcam_path', None),
            'duration': duration,
            'total_frames': len(self.frames),
            'total_webcam_frames': len(self.webcam_frames)
        }

    def take_screenshot(self):
        """Instant screenshot lo"""
        with mss.mss() as sct:
            screenshot = sct.grab(sct.monitors[1])
            frame = np.array(screenshot)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

            path = os.path.join(
                self.output_dir,
                f'screenshot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
            )
            cv2.imwrite(path, frame)
            return path

    def get_current_frame(self):
        """Current frame do for real-time analysis"""
        if self.webcam_frames:
            return self.webcam_frames[-1]['frame']
        return None
