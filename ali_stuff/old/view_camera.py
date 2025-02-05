import asyncio
import base64
import cv2
import requests
from loguru import logger
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from av import VideoFrame

class VideoDisplay(VideoStreamTrack):
    def __init__(self, track: MediaStreamTrack):
        super().__init__()
        self.track = track

    async def recv(self):
        frame = await self.track.recv()
        
        # Convert frame to OpenCV format and display
        img = frame.to_ndarray(format="bgr24")
        
        # Display the frame
        cv2.imshow("Robot Camera", img)
        cv2.waitKey(1)
        
        return frame

async def main():
    # WebRTC stream URL for the robot
    SERVER_URL = "http://10.33.11.170:8083/stream/s1/channel/0/webrtc?uuid=s1&channel=0"
    
    # Initialize WebRTC connection
    pc = RTCPeerConnection()
    pc.addTransceiver("video", direction="recvonly")
    
    @pc.on("track")
    def on_track(track):
        if track.kind == "video":
            display = VideoDisplay(track)
            asyncio.ensure_future(display_video(display))
    
    # Create and set local description
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    
    # Encode and send SDP offer
    sdp_offer_base64 = base64.b64encode(pc.localDescription.sdp.encode("utf-8")).decode("utf-8")
    
    # Send to server
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
    }
    
    try:
        response = requests.post(SERVER_URL, 
                               headers=headers,
                               data={"data": sdp_offer_base64}, 
                               verify=False)
        response.raise_for_status()
        sdp_answer = base64.b64decode(response.text).decode("utf-8")
        
        # Set remote description
        await pc.setRemoteDescription(
            RTCSessionDescription(sdp=sdp_answer, type="answer")
        )
        
        logger.info("Connected to camera stream")
        
        # Keep running until interrupted
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stream interrupted by user")
            
    except Exception as e:
        logger.error(f"Error connecting to camera: {e}")
        logger.error("Traceback:", exc_info=True)
    
    finally:
        cv2.destroyAllWindows()
        await pc.close()

async def display_video(display):
    try:
        while True:
            await display.recv()
    except Exception as e:
        logger.error(f"Display error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program terminated by user") 