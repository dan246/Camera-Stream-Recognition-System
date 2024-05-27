import os
import redis
import cv2
import threading
import numpy as np
from time import time, sleep, localtime, strftime
from datetime import datetime, timedelta
import os
import base64
import os
import requests
from io import BytesIO
from ultralytics import YOLO
import json

DELDAYS = os.getenv('DELDAYS')
# 初始化 Redis 連線
redis_host = 'redis'
redis_port = 6379
r = redis.Redis(host=redis_host, port=redis_port, db=0)


# Function to download the model weights if not already downloaded
def download_model_weights(url, save_path):
    if not os.path.exists(save_path):
        print("Downloading model weights...")
        response = requests.get(url)
        if response.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(response.content)
            print("Model weights downloaded successfully.")
        else:
            print("Failed to download model weights.")

# Function to predict using YOLO model and store results in Redis
def predict_with_yolo(model, image_paths, redis_client):
    results = model(image_paths)
    for result, image_path in zip(results, image_paths):
        camera_id = image_path.split("/")[-2]  # Assuming camera ID is part of the path
        redis_key = f"camera:{camera_id}:latest_detection"
        redis_client.set(redis_key, str(result), ex=86400)  # Store results with a 1-day expiration
    return results

def remove_old_files(base_path, days=DELDAYS):
    """移除指定路徑中特定日期的檔案"""
    target_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
    
    # 遍歷每個攝影機的目錄
    for camera_name in os.listdir(base_path):
        camera_path = os.path.join(base_path, camera_name)
        if os.path.isdir(camera_path):  # 確保是目錄
            target_path = os.path.join(camera_path, target_date)
            if os.path.exists(target_path):
                for root, dirs, files in os.walk(target_path, topdown=False):
                    for file in files:
                        os.remove(os.path.join(root, file))
                        print(f"Deleted file: {os.path.join(root, file)}")
                    for dir in dirs:
                        os.rmdir(os.path.join(root, dir))
                        print(f"Deleted directory: {os.path.join(root, dir)}")
                print(f"All files from {target_path} have been deleted.")
                # 檢查並刪除現在應該是空的根目錄
                if not os.listdir(target_path):
                    os.rmdir(target_path)
                    print(f"Deleted empty directory: {target_path}")
                print(f"All files from {target_path} have been deleted.")
            else:
                print(f"No files found for date {target_date} in {camera_path}.")


def fetch_frame(camera_id, camera_url, worker_key, stop_event):
    cap = cv2.VideoCapture(camera_url)
    reconnect_interval = 30  # 重新連線時間
    frame_count = 0  # 幀計數器
    last_time = time()  # 記錄上次時間戳
    file_path = None  # 初始化 file_path 變量
    model_weights_url = "MODEL_URL"
    model_weights_save_path = base64.b64encode(model_weights_url.encode()).decode() + ".pt"

    # Download model weights
    download_model_weights(model_weights_url, model_weights_save_path)

    # Load YOLO model
    model = YOLO(model_weights_save_path)
    
    while not stop_event.is_set():
        if not cap.isOpened():
            print(f"Camera connection lost. Reconnecting in {reconnect_interval} seconds...")
            cap.open(camera_url)
            sleep(reconnect_interval)
            r.set(f'camera_{camera_id}_status', 'False')
            continue

        ret, frame = cap.read()
        if ret:
            
            results = model.track(source=frame, conf=0.3, iou=0.5, show=False)
            boxes = results[0].boxes
            if len(boxes.cls) > 0:
                try:
                    cls = [model.names[int(item)] for item in boxes.cls]
                    id = [str(int(item)) for item in boxes.id]
                    xywh = [[str(int(xywh)) for xywh in item] for item in boxes.xywh]
                    xywh_serialized = json.dumps(xywh)
                except:
                    id = []
                    xywh_serialized = json.dumps([])
                    cls = []
            else:
                id = []
                xywh_serialized = json.dumps([])
                cls = []
            frame_count += 1  # 更新幀計數器
            current_time = time()
            elapsed = current_time - last_time

            if elapsed >= 1.0:  # 每隔一秒計算 FPS
                fps = frame_count / elapsed
                r.set(f'camera_{camera_id}_fps', fps)
                print(f"Camera {camera_id} FPS: {fps}")
                frame_count = 0  # 重置幀計數器
                last_time = current_time

            timestamp = current_time + 8 * 3600  # 加 8 小時
            timestamp_str = strftime("%Y%m%d%H%M%S", localtime(timestamp))
            
            # 每100幀存一次圖
            if frame_count % 100 == 0:
                folder_path = os.path.join('frames', str(camera_id), timestamp_str[:8], timestamp_str[8:10])
                os.makedirs(folder_path, exist_ok=True)
                file_name = f"{timestamp_str}.jpg"
                file_path = os.path.join(folder_path, file_name)
                cv2.imwrite(file_path, frame)
                print(f"Saved frame: {file_path}")
                r.set(f'camera_{camera_id}_latest_frame_path', file_path)  # 儲存最新圖片路徑至 Redis

            _, buffer = cv2.imencode('.jpg', frame)
            image_data = buffer.tobytes()
            r.set(f'camera_{camera_id}_latest_frame', image_data)
            r.set(f'camera_{camera_id}_status', 'True')
            r.set(f'camera_{camera_id}_last_timestamp', timestamp_str)
            r.set(f'camera_{camera_id}_url', camera_url)

            r.set(f'camera_{camera_id}_last_cls', ','.join(cls))
            r.set(f'camera_{camera_id}_last_id', ','.join(id))
            r.set(f'camera_{camera_id}_last_xywh', xywh_serialized)
        else:
            print("Error reading frame. Retrying...")
            cap.release()
            cap.open(camera_url)
            print(f"Reconnecting to camera at URL: {camera_url}")
            sleep(1)
            r.set(f'camera_{camera_id}_status', 'False')

        # sleep(0.1)  # 每0.1秒檢查一次

    cap.release()


def monitor_cameras(worker_key, camera_urls):
    threads = []
    stop_events = []
    for url in camera_urls:
        url_parts = url.decode('utf-8').split('|')
        camera_id = url_parts[0]
        camera_url = url_parts[1]
        stop_event = threading.Event()
        thread = threading.Thread(target=fetch_frame, args=(camera_id, camera_url, worker_key, stop_event))
        thread.start()
        threads.append((thread, stop_event))
    return threads

def setup_camera_manager():
    # 每天檢查一次是否有需要刪除的檔案
    threading.Timer(10, setup_camera_manager).start()
    remove_old_files('/app/frames')  # 調整路徑至所有攝影機的根目錄



def main():

    # setup_camera_manager() 
    worker_id = os.getenv('WORKER_ID')
    if worker_id is None:
        raise ValueError("WORKER_ID environment variable is not set.")
    worker_key = f'worker_{worker_id}_urls'

    pubsub = r.pubsub()
    pubsub.subscribe([f'{worker_key}_update'])

    current_urls = set(r.smembers(worker_key))
    threads = monitor_cameras(worker_key, current_urls)

    try:
        for message in pubsub.listen():
            if message['type'] == 'message':
                new_urls = set(r.smembers(worker_key))
                if new_urls != current_urls:
                    for _, stop_event in threads:
                        stop_event.set()
                    for thread, _ in threads:
                        thread.join()
                    threads = monitor_cameras(worker_key, new_urls)
                    current_urls = new_urls
    finally:
        pubsub.close()




if __name__ == "__main__":
    main()
