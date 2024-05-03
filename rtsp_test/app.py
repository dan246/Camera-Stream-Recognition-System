import os
import redis
import cv2
import threading
import numpy as np
from time import time, sleep, localtime, strftime
from io import BytesIO
import csv

# 初始化 Redis 連線
redis_host = 'redis'
redis_port = 6379
r = redis.Redis(host=redis_host, port=redis_port, db=0)


def fetch_frame(camera_id, camera_url, worker_key, stop_event):
    cap = cv2.VideoCapture(camera_url)
    reconnect_interval = 30  # 重新連線時間
    frame_count = 0  # 新增幀計數器

    while not stop_event.is_set():
        if not cap.isOpened():
            print(f"Camera connection lost. Reconnecting in {reconnect_interval} seconds...")
            cap.open(camera_url)
            sleep(reconnect_interval)
            r.set(f'camera_{camera_id}_status', 'False')
            continue

        ret, frame = cap.read()
        if ret:
            frame_count += 1  # 更新幀計數器
            timestamp = time() + 8 * 3600  # 加 8 小時
            timestamp_str = strftime("%Y%m%d%H%M%S", localtime(timestamp))
            
            # 每10幀存一次圖
            if frame_count % 10 == 0:
                folder_path = os.path.join('frames', str(camera_id), timestamp_str[:8], timestamp_str[8:10])
                os.makedirs(folder_path, exist_ok=True)
                file_name = f"{timestamp_str}.jpg"
                file_path = os.path.join(folder_path, file_name)
                cv2.imwrite(file_path, frame)
                print(f"Saved frame: {file_path}")

            _, buffer = cv2.imencode('.jpg', frame)
            image_data = buffer.tobytes()
            r.set(f'camera_{camera_id}_latest_frame', image_data)
            if frame_count % 10 == 0:
                r.set(f'camera_{camera_id}_latest_frame_path', file_path)
            r.set(f'camera_{camera_id}_status', 'True')
            r.set(f'camera_{camera_id}_last_timestamp', timestamp_str)
        else:
            print("Error reading frame. Retrying...")
            cap.release()
            cap.open(camera_url)
            print(f"Reconnecting to camera at URL: {camera_url}")
            sleep(1)
            r.set(f'camera_{camera_id}_status', 'False')
            frame_count = 0  # 重置幀計數器，因為相機已重新連線

        sleep(0.1)  # 每0.1秒檢查一次

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
    timer = threading.Timer(1, setup_camera_manager)  # 重新設定 Timer
    timer.start()


def write_cameras_info_to_csv():
    header = ['Worker ID', 'Camera Name', 'Camera URL']
    with open('workers_cameras_info.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)
        for worker_id in range(1, 7):  # 更新這裡以包括實際的 worker ID 範圍
            worker_key = f'worker_{worker_id}_urls'
            camera_urls = r.smembers(worker_key)
            for cam in camera_urls:
                parts = cam.decode('utf-8').split('|')
                camera_id, camera_name, camera_url = parts[0], parts[1], parts[2]
                writer.writerow([worker_id, camera_name, camera_url])

def main():
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
