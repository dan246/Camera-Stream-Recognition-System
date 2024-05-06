# Camera-Stream-Recognition-System

This project utilizes Python and Redis to manage and recognize multiple camera streams. Key features include real-time capturing of camera streams, object recognition, image saving, and dynamic updating of stream URLs.

The system can handle over 100 camera streams simultaneously. Redis distributes tasks evenly across workers, so if the system feels slow or unresponsive, simply add more workers and adjust the settings in `camera_100`'s `camera_manager` (consider setting environment variables dynamically with docker-compose).

![Untitled](https://github.com/dan246/Camera-Stream-Recognition-System/assets/72447312/895eb525-3180-4f74-a484-de83e808aee9)

## Features

- **Stream Capture**: Continuously captures images from multiple camera feeds.
- **Object Recognition**: Utilizes deep learning models to recognize objects in captured images.
- **Video Playback**: Video playback functionality can be customized as needed.
- **Data Archiving**: Captured images are stored locally and path information is synchronized to Redis.
- **Dynamic Updates**: Dynamically updates the list of camera streams and synchronizes across multiple worker nodes using Redis.

## Getting Started

The following will help you deploy and run the system on your local environment.

### Environment

- Docker
- Docker Compose
- Python 3.8 or higher
- GPU

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourgithub/camera-stream-handler.git
   cd camera-stream-handler
   ```
2. **Build and start the system using Docker Compose**
  ```bash
  docker-compose build
  docker-compose up -d
  ```

### Notes
1. The docker-compose file can be customized to include additional containers as neededExamples include DB, frontend web, nginx, etc. This setup primarily involves the backend and a minimal web interface, with most interactions occurring via API.

2. After starting, run addw1 (configure the connection in camera_100's camera_manager if a DB is used)If there is no DB, since Redis does not register events until after startup, execute addw1.py to register events and allocate containers.

3. Camera input data in Redis should be in the format of id + camera_url

4. Images are stored in the frames folder under Redisframes is also mounted to camera_100 for retrieval.

5. RTSP URLs require conversion using go2RTC

Ongoing modifications and optimizations are in progress. 
