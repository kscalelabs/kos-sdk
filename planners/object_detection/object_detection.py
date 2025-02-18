import asyncio
import base64
import logging
from typing import Dict, Optional, Tuple, Any
import math

import cv2
import numpy as np
import requests
from ultralytics import YOLO
from aiortc import (
    MediaStreamTrack,
    RTCPeerConnection,
    RTCSessionDescription,
    VideoStreamTrack,
)
from av import VideoFrame

# Configure logging to suppress ffmpeg warnings
logging.getLogger("ffmpeg").setLevel(logging.ERROR)

robot_ip = "10.33.12.37"

# Server configuration for WebRTC stream
SERVER_URL = f"http://{robot_ip}:8083/stream/s1/channel/0/webrtc?uuid=s1&channel=0"
# Use YOLOv8n model from Ultralytics
MODEL_NAME = "yolov8n.pt"  # Changed from local path to model name

class DetectionConfig:
    """Configuration parameters for object detection and display.
    
    This class centralizes all adjustable parameters for the detection system,
    making it easier to tune the system's behavior.
    """
    def __init__(self):
        # Detection parameters
        self.process_interval = 3      # Process every Nth frame for performance
        self.conf_threshold = 0.5      # Minimum confidence for valid detections
        self.detection_persistence = 5  # Number of frames to keep detections
        self.smoothing_alpha = 0.7     # Smoothing factor (0.7 = 70% previous + 30% new)
        
        # Display settings
        self.display_width = 960       # Output video width
        self.display_height = 540      # Output video height
        self.inference_size = 640      # Input size for YOLO model
        
        # Camera parameters for distance calculation
        self.focal_length = 500        # Camera focal length in pixels
        self.known_width = 600         # Reference object width in mm
        
        # Visualization colors (in BGR format)
        self.line_color = (0, 255, 255)    # Yellow for navigation lines
        self.box_color = (0, 255, 0)       # Green for bounding boxes
        self.text_color = (255, 255, 255)  # White for text

class NavigationInfo:
    """Container for navigation-related measurements.
    
    Stores calculated distances and angles to detected objects,
    providing structured access to navigation data.
    """
    def __init__(self, distance: float, bearing: float, vertical_angle: float, center: Tuple[int, int]):
        self.distance = distance          # Distance to object in mm
        self.bearing = bearing            # Horizontal angle to object (negative=left, positive=right)
        self.vertical_angle = vertical_angle  # Vertical angle to object (negative=up, positive=down)
        self.center = center             # Object center coordinates (x, y)

class VideoDisplay(VideoStreamTrack):
    """Main class for video processing and object detection.
    
    Handles real-time video stream processing, object detection,
    and visualization of detection results with navigation information.
    """
    def __init__(self, track: MediaStreamTrack) -> None:
        """Initialize the video display track with YOLO detection.

        Args:
            track: The source video track to display.
        """
        super().__init__()
        self.track = track
        self.config = DetectionConfig()
        # This will automatically download the model if not present
        self.model = YOLO(MODEL_NAME)
        
        # State tracking variables
        self.frame_count = 0              # Counter for processed frames
        self.last_detections = []         # Store recent valid detections
        self.last_detection_frame = 0     # Frame number of last detection
        self.prev_boxes = {}              # Store previous box positions for smoothing
        self.current_target = None        # Current navigation target
        
        # Navigation reference points
        self.horizon_line_y = self.config.display_height // 2  # Horizontal center line
        self.center_x = self.config.display_width // 2         # Vertical center line

    def calculate_navigation_info(self, box: np.ndarray) -> NavigationInfo:
        """Calculate distance and angles to detected object.
        
        Uses similar triangles principle for distance calculation and
        trigonometry for angle calculations.
        
        Args:
            box: Bounding box coordinates [x1, y1, x2, y2]
            
        Returns:
            NavigationInfo object with distance and angle measurements
        """
        x1, y1, x2, y2 = map(int, box)
        
        # Calculate distance using similar triangles principle:
        # real_width / distance = pixel_width / focal_length
        object_width_pixels = x2 - x1
        distance = (self.config.known_width * self.config.focal_length) / object_width_pixels
        
        # Calculate horizontal bearing (negative = left, positive = right)
        box_center_x = (x1 + x2) // 2
        pixels_from_center = box_center_x - self.center_x
        bearing = math.degrees(math.atan2(pixels_from_center, self.config.focal_length))
        
        # Calculate vertical angle (negative = up, positive = down)
        box_bottom_y = y2
        pixels_from_horizon = box_bottom_y - self.horizon_line_y
        vertical_angle = math.degrees(math.atan2(pixels_from_horizon, self.config.focal_length))
        
        return NavigationInfo(distance, bearing, vertical_angle, (box_center_x, box_bottom_y))

    def smooth_detection_box(self, new_box: np.ndarray, class_id: int) -> np.ndarray:
        """Apply exponential smoothing to box coordinates to reduce jitter.
        
        Smooths detection boxes over time using exponential moving average:
        smooth = alpha * previous + (1 - alpha) * new
        
        Args:
            new_box: New detection box coordinates
            class_id: Class ID to track different objects separately
            
        Returns:
            Smoothed box coordinates
        """
        if class_id not in self.prev_boxes:
            self.prev_boxes[class_id] = new_box
            return new_box
            
        smooth_box = []
        for i, coord in enumerate(new_box):
            prev = self.prev_boxes[class_id][i]
            smooth = self.config.smoothing_alpha * prev + (1 - self.config.smoothing_alpha) * coord
            smooth_box.append(smooth)
            
        self.prev_boxes[class_id] = smooth_box
        return np.array(smooth_box)

    def draw_navigation_overlay(self, img: np.ndarray, nav_info: Optional[NavigationInfo]) -> np.ndarray:
        """Draw navigation information and reference lines."""
        overlay = img.copy()
        
        # Draw reference lines
        cv2.line(overlay, (0, self.horizon_line_y), 
                (self.config.display_width, self.horizon_line_y),
                self.config.line_color, 2)
        cv2.line(overlay, (self.center_x, 0), 
                (self.center_x, self.config.display_height),
                self.config.line_color, 2)
        
        cv2.addWeighted(overlay, 0.5, img, 0.5, 0, img)
        
        if nav_info and nav_info.distance > 0:
            # Draw target line
            cv2.line(img, (self.center_x, self.horizon_line_y), 
                    nav_info.center, self.config.line_color, 3)
            
            # Draw measurements
            texts = [
                f"Distance: {nav_info.distance:.1f}mm",
                f"Bearing: {nav_info.bearing:.1f}",
                f"Vertical: {nav_info.vertical_angle:.1f}"
            ]
            
            for i, text in enumerate(texts):
                cv2.putText(img, text, (10, 30 + i*25),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                           self.config.line_color, 2)
        
        return img

    async def process_frame(self, frame: VideoFrame) -> np.ndarray:
        """Process a single frame with object detection."""
        img = frame.to_ndarray(format="bgr24")
        img = cv2.resize(img, (self.config.display_width, self.config.display_height), 
                        interpolation=cv2.INTER_LANCZOS4)
        
        if self.frame_count % self.config.process_interval == 0:
            results = self.model.predict(img, conf=self.config.conf_threshold, 
                                      imgsz=self.config.inference_size)
            self.update_detections(results)
            
        return self.draw_frame(img)

    def update_detections(self, results: Any) -> None:
        """Update detection state from new results."""
        self.last_detections = []
        for result in results:
            boxes = result.boxes.cpu().numpy()
            for box in boxes:
                confidence = float(box.conf[0])
                if confidence > self.config.conf_threshold:
                    # Apply smoothing to box coordinates
                    class_id = int(box.cls[0])
                    smooth_box = self.smooth_detection_box(box.xyxy[0], class_id)
                    
                    self.last_detections.append({
                        'box': smooth_box,
                        'conf': confidence,
                        'class_id': class_id,
                        'frame': self.frame_count
                    })
        
        if self.last_detections:
            self.last_detection_frame = self.frame_count

    def draw_frame(self, img: np.ndarray) -> np.ndarray:
        """Draw all detections and overlays on the frame."""
        if not img.size or img.shape[0] == 0 or img.shape[1] == 0:
            raise ValueError("Invalid image dimensions")
            
        img_draw = img.copy()
        nav_info = None
        
        # Remove old detections
        current_detections = []
        for det in self.last_detections:
            age = self.frame_count - det['frame']
            if age <= self.config.detection_persistence:
                current_detections.append(det)
        
        self.last_detections = current_detections
        
        # Find most confident detection for navigation
        if self.last_detections:
            most_confident = max(self.last_detections, key=lambda x: x['conf'])
            nav_info = self.calculate_navigation_info(most_confident['box'])
            self.current_target = nav_info
        
        # Draw all detections
        for det in self.last_detections:
            x1, y1, x2, y2 = map(int, det['box'])
            class_name = self.model.names[det['class_id']]
            
            # Draw bounding box
            cv2.rectangle(img_draw, (x1, y1), (x2, y2), 
                         self.config.box_color, 6)
            
            # Draw label
            label = f'{class_name} {det["conf"]:.2f}'
            font_scale = 1.0
            font_thickness = 2
            font = cv2.FONT_HERSHEY_SIMPLEX
            
            (label_width, label_height), _ = cv2.getTextSize(
                label, font, font_scale, font_thickness
            )
            
            padding = 7
            cv2.rectangle(
                img_draw,
                (x1, y1 - label_height - 2*padding),
                (x1 + label_width + 2*padding, y1),
                self.config.box_color,
                -1
            )
            
            cv2.putText(
                img_draw,
                label,
                (x1 + padding, y1 - padding),
                font,
                font_scale,
                self.config.text_color,
                font_thickness
            )
        
        # Draw navigation overlay
        img_draw = self.draw_navigation_overlay(img_draw, nav_info)
        return img_draw

    async def recv(self) -> MediaStreamTrack:
        """Receive and process video frames."""
        try:
            frame = await self.track.recv()
            
            # Ensure frame has valid dimensions
            if frame.width <= 0 or frame.height <= 0:
                raise ValueError("Invalid frame dimensions")
                
            img = await self.process_frame(frame)
            
            # Verify processed image dimensions
            if img.shape[0] <= 0 or img.shape[1] <= 0:
                raise ValueError("Invalid processed image dimensions")
            
            cv2.namedWindow("WebRTC Video with Object Detection", cv2.WINDOW_NORMAL)
            cv2.imshow("WebRTC Video with Object Detection", img)
            cv2.waitKey(1)
            
            new_frame = VideoFrame(width=frame.width, height=frame.height)
            new_frame.from_ndarray(img, format="bgr24")
            new_frame.pts = frame.pts
            new_frame.time_base = frame.time_base
            
            self.frame_count += 1
            return new_frame
            
        except Exception as e:
            logging.error(f"Error processing frame: {e}")
            raise

    def get_navigation_target(self):
        """Return current navigation target information."""
        return self.current_target

async def create_sdp_offer(pc: RTCPeerConnection) -> str:
    """Create and encode an SDP offer.

    Args:
        pc: The peer connection to create the offer for.

    Returns:
        The base64 encoded SDP offer.
    """
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    return base64.b64encode(pc.localDescription.sdp.encode("utf-8")).decode("utf-8")

def send_sdp_to_server(base64_sdp: str) -> str:
    """Send SDP offer to server and get answer.

    Args:
        base64_sdp: The base64 encoded SDP offer.

    Returns:
        The decoded SDP answer from the server.

    Raises:
        requests.exceptions.RequestException: If the server request fails.
    """
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
    }
    response = requests.post(SERVER_URL, headers=headers, 
                           data={"data": base64_sdp}, verify=False)
    response.raise_for_status()
    return base64.b64decode(response.text).decode("utf-8")

async def display_video(display: VideoDisplay) -> None:
    """Coroutine to continuously receive and display video frames.

    Args:
        display: The video display track to receive frames from.
    """
    try:
        while True:
            await display.recv()
    except Exception as e:
        print(f"Display video error: {e}")

async def main() -> None:
    """Main function to set up and run the WebRTC video stream with object detection."""
    # Initialize peer connection
    pc = RTCPeerConnection()
    pc.addTransceiver("video", direction="recvonly")

    @pc.on("track")
    def on_track(track: MediaStreamTrack) -> None:
        """Handle incoming media tracks.

        Args:
            track: The received media track.
        """
        if track.kind == "video":
            display = VideoDisplay(track)
            asyncio.ensure_future(display_video(display))

    # Create and set local description
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    # Send offer to server
    sdp_offer_base64 = base64.b64encode(pc.localDescription.sdp.encode("utf-8")).decode("utf-8")
    sdp_answer = send_sdp_to_server(sdp_offer_base64)

    # Set remote description
    await pc.setRemoteDescription(RTCSessionDescription(sdp=sdp_answer, type="answer"))

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        await pc.close()

if __name__ == "__main__":
    asyncio.run(main())