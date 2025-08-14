import cv2
import numpy as np
import logging
from typing import Dict, Optional, Tuple
import time

logger = logging.getLogger(__name__)

class VisionService:
    def __init__(self):
        self.mediapipe_available = False
        self.face_cascade = None
        
        # Try to initialize MediaPipe
        try:
            import mediapipe as mp
            self.mp_face_detection = mp.solutions.face_detection
            self.mp_pose = mp.solutions.pose
            self.mp_hands = mp.solutions.hands
            self.mp_drawing = mp.solutions.drawing_utils
            
            self.face_detection = self.mp_face_detection.FaceDetection(
                model_selection=0, min_detection_confidence=0.5
            )
            self.pose = self.mp_pose.Pose(
                static_image_mode=False,
                model_complexity=1,
                smooth_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
            
            self.mediapipe_available = True
            logger.info("MediaPipe initialized successfully")
            
        except ImportError:
            logger.warning("MediaPipe not available, using OpenCV fallback")
            # Fallback to OpenCV Haar cascades
            try:
                self.face_cascade = cv2.CascadeClassifier(
                    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                )
                logger.info("OpenCV face detection initialized")
            except Exception as e:
                logger.error(f"Error initializing OpenCV face detection: {e}")
        except Exception as e:
            logger.error(f"Error initializing MediaPipe: {e}")
    
    def analyze_frame(self, frame: np.ndarray) -> Dict:
        """Analyze a video frame for behavioral metrics"""
        if self.mediapipe_available:
            return self._analyze_with_mediapipe(frame)
        else:
            return self._analyze_with_opencv(frame)
    
    def _analyze_with_mediapipe(self, frame: np.ndarray) -> Dict:
        """Analyze frame using MediaPipe"""
        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            height, width = frame.shape[:2]
            
            metrics = {
                'face_detected': False,
                'eye_contact_score': 0.0,
                'posture_score': 0.0,
                'gesture_count': 0,
                'attention_score': 0.0,
                'timestamp': time.time()
            }
            
            # Face detection
            face_results = self.face_detection.process(rgb_frame)
            if face_results.detections:
                metrics['face_detected'] = True
                
                # Calculate eye contact score based on face position
                detection = face_results.detections[0]
                bbox = detection.location_data.relative_bounding_box
                face_center_x = bbox.xmin + bbox.width / 2
                face_center_y = bbox.ymin + bbox.height / 2
                
                # Eye contact score based on how centered the face is
                center_distance = np.sqrt((face_center_x - 0.5)**2 + (face_center_y - 0.5)**2)
                metrics['eye_contact_score'] = max(0, 1 - center_distance * 2)
            
            # Pose detection for posture analysis
            pose_results = self.pose.process(rgb_frame)
            if pose_results.pose_landmarks:
                landmarks = pose_results.pose_landmarks.landmark
                
                # Calculate posture score based on shoulder alignment
                left_shoulder = landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER]
                right_shoulder = landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER]
                
                if left_shoulder.visibility > 0.5 and right_shoulder.visibility > 0.5:
                    shoulder_diff = abs(left_shoulder.y - right_shoulder.y)
                    metrics['posture_score'] = max(0, 1 - shoulder_diff * 10)
            
            # Hand detection for gesture counting
            hand_results = self.hands.process(rgb_frame)
            if hand_results.multi_hand_landmarks:
                metrics['gesture_count'] = len(hand_results.multi_hand_landmarks)
            
            # Overall attention score
            metrics['attention_score'] = (
                metrics['eye_contact_score'] * 0.4 +
                metrics['posture_score'] * 0.3 +
                min(metrics['gesture_count'] / 2, 1) * 0.3
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error in MediaPipe analysis: {e}")
            return self._get_default_metrics()
    
    def _analyze_with_opencv(self, frame: np.ndarray) -> Dict:
        """Analyze frame using OpenCV (fallback)"""
        try:
            metrics = {
                'face_detected': False,
                'eye_contact_score': 0.0,
                'posture_score': 0.5,  # Default neutral score
                'gesture_count': 0,
                'attention_score': 0.0,
                'timestamp': time.time()
            }
            
            if self.face_cascade is not None:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(gray, 1.1, 4)
                
                if len(faces) > 0:
                    metrics['face_detected'] = True
                    
                    # Use largest face
                    largest_face = max(faces, key=lambda x: x[2] * x[3])
                    x, y, w, h = largest_face
                    
                    # Calculate eye contact score based on face position
                    face_center_x = (x + w/2) / frame.shape[1]
                    face_center_y = (y + h/2) / frame.shape[0]
                    
                    center_distance = np.sqrt((face_center_x - 0.5)**2 + (face_center_y - 0.5)**2)
                    metrics['eye_contact_score'] = max(0, 1 - center_distance * 2)
                    
                    # Simple attention score
                    metrics['attention_score'] = metrics['eye_contact_score'] * 0.7 + 0.3
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error in OpenCV analysis: {e}")
            return self._get_default_metrics()
    
    def _get_default_metrics(self) -> Dict:
        """Return default metrics when analysis fails"""
        return {
            'face_detected': False,
            'eye_contact_score': 0.0,
            'posture_score': 0.0,
            'gesture_count': 0,
            'attention_score': 0.0,
            'timestamp': time.time()
        }
    
    def is_vision_available(self) -> bool:
        """Check if computer vision services are available"""
        return self.mediapipe_available or self.face_cascade is not None
    
    def get_vision_status(self) -> Dict:
        """Get status of computer vision services"""
        return {
            'mediapipe_available': self.mediapipe_available,
            'opencv_available': self.face_cascade is not None,
            'fully_functional': self.mediapipe_available
        }

