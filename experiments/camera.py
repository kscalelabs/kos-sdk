import asyncio
import base64
import logging
import mediapipe as mp
import cv2
import requests
from aiortc import (
    MediaStreamTrack,
    RTCPeerConnection,
    RTCSessionDescription,
    VideoStreamTrack,
)
import numpy as np

# Configure logging
logging.basicConfig(level=logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("aiortc").setLevel(logging.WARNING)

# Server URL (replace with your actual server URL)
SERVER_URL = "http://192.168.42.1:8083/stream/s1/channel/0/webrtc?uuid=s1&channel=0"

# Initialize MediaPipe
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils
pose = mp_pose.Pose(
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
    model_complexity=0,  # Use lightweight model for better performance
)


def send_sdp_to_server(base64_sdp: str) -> str:
    """Send SDP offer to server and get answer."""
    try:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        }
        data = {"data": base64_sdp}

        response = requests.post(
            SERVER_URL, headers=headers, data=data, verify=False, timeout=10
        )
        response.raise_for_status()

        return base64.b64decode(response.text).decode("utf-8")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send SDP to server: {e}")
        raise


class VideoDisplay(VideoStreamTrack):
    def __init__(self, track: MediaStreamTrack) -> None:
        super().__init__()
        self.track = track
        self.person_data = {"detected": False, "position": None, "pose_landmarks": None}

    async def recv(self) -> MediaStreamTrack:
        try:
            frame = await self.track.recv()
            img = frame.to_ndarray(format="bgr24")

            rgb_frame = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb_frame)

            self.person_data["detected"] = False

            if results.pose_landmarks:
                self.person_data["detected"] = True

                mp_drawing.draw_landmarks(
                    img,
                    results.pose_landmarks,
                    mp_pose.POSE_CONNECTIONS,
                    mp_drawing.DrawingSpec(
                        color=(245, 117, 66), thickness=2, circle_radius=2
                    ),
                    mp_drawing.DrawingSpec(
                        color=(245, 66, 230), thickness=2, circle_radius=2
                    ),
                )

                self.person_data["pose_landmarks"] = results.pose_landmarks

                h, w, _ = img.shape
                hip = results.pose_landmarks.landmark[mp_pose.PoseLandmark.LEFT_HIP]
                self.person_data["position"] = (int(hip.x * w), int(hip.y * h))

                left_wrist = results.pose_landmarks.landmark[
                    mp_pose.PoseLandmark.LEFT_WRIST
                ].y
                right_wrist = results.pose_landmarks.landmark[
                    mp_pose.PoseLandmark.RIGHT_WRIST
                ].y
                shoulder = results.pose_landmarks.landmark[
                    mp_pose.PoseLandmark.LEFT_SHOULDER
                ].y

                if left_wrist < shoulder or right_wrist < shoulder:
                    cv2.putText(
                        img,
                        "Hands Raised!",
                        (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1,
                        (0, 255, 0),
                        2,
                    )

            cv2.imshow("WebRTC Video with Pose Detection", img)
            key = cv2.waitKey(1)
            if key == 27:  # ESC key
                raise KeyboardInterrupt

            new_frame = frame.replace(data=img)
            return new_frame

        except Exception as e:
            if isinstance(e, KeyboardInterrupt):
                raise
            logging.error(f"Error in recv: {e}")
            return frame  # Return original frame on error

    def get_person_data(self):
        """Return the current person detection data"""
        return self.person_data


async def run_display(display):
    """Wrapper for display loop with proper error handling"""
    try:
        while True:
            await display.recv()
    except KeyboardInterrupt:
        logging.info("Display stopped by user")
    except Exception as e:
        logging.error(f"Display error: {e}")


async def main() -> None:
    pc = None
    try:
        # Initialize peer connection
        pc = RTCPeerConnection()

        # Add video transceiver
        pc.addTransceiver("video", direction="recvonly")

        display = None

        @pc.on("track")
        def on_track(track: MediaStreamTrack) -> None:
            nonlocal display
            if track.kind == "video":
                display = VideoDisplay(track)
                asyncio.ensure_future(run_display(display))

        # Create and set local description
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)

        # Send offer to server
        sdp_offer_base64 = base64.b64encode(
            pc.localDescription.sdp.encode("utf-8")
        ).decode("utf-8")
        sdp_answer = send_sdp_to_server(sdp_offer_base64)

        # Set remote description
        await pc.setRemoteDescription(
            RTCSessionDescription(sdp=sdp_answer, type="answer")
        )

        # Main loop
        while True:
            if display and display.get_person_data()["detected"]:
                person_data = display.get_person_data()
                print(f"Person detected at position: {person_data['position']}")
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        logging.info("Stopped by user")
    except Exception as e:
        logging.error(f"Error in main: {e}")
    finally:
        # Cleanup
        cv2.destroyAllWindows()
        if pc:
            await pc.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Program terminated by user")
    except Exception as e:
        logging.error(f"Program error: {e}")
