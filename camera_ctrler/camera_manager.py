import threading
import redis
import requests
import logging
import os
import time

# 預設設置工作器 ID
worker_id = int(os.getenv('WORKER_ID', 1))
SERVERIP = os.getenv('SERVERIP')
ACCOUNT = os.getenv('ACCOUNT')
PASSWORD = os.getenv('PASSWORD')

class CameraManager:
    def __init__(self):
        self.redis_client = redis.Redis(host='redis', port=6379, db=0)
        self.worker_id = worker_id
        self.worker_key = f'worker_{self.worker_id}_urls'
        self.SERVERIP = SERVERIP
        self.ACCOUNT = ACCOUNT
        self.PASSWORD = PASSWORD
        self.num_workers = 3  # 3個 worker

    def get_token(self):
        url = f"http://{self.SERVERIP}:7000/api/1/user/login"
        payload = {'account': self.ACCOUNT, 'password': self.PASSWORD}
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            access_token = response.json().get('access_token', None)
            return access_token
        else:
            logging.error(f"登入失敗，狀態碼：{response.status_code}")
            return None

    def clear_old_cameras(self):
        # 清除所有工作器的攝影機資料
        for worker_id in range(1, self.num_workers + 1):
            worker_key = f'worker_{worker_id}_urls'
            self.redis_client.delete(worker_key)
            logging.info(f"Cleared old cameras for worker {worker_id}.")

    def fetch_and_update_cameras(self):
        self.clear_old_cameras()
        token = self.get_token()
        if not token:
            logging.error("無法取得 Token，中止操作。")
            return

        # camera data in db
        url = f"http://{self.SERVERIP}:7000/api/1/camera/get_camera_list"
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            camera_data = response.json().get("data", [])
            for camera in camera_data:
                if camera['camera_type'] == 1 and camera['camera_url'].startswith("http"):
                    worker_id = int(camera['camera_id']) % self.num_workers + 1
                    worker_key = f'worker_{worker_id}_urls'
                    self.redis_client.sadd(worker_key, f"{camera['camera_id']}|{camera['camera_url']}")
                    logging.info(f"Added camera {camera['camera_id']} to Redis at worker {worker_id}.")

            # 發布更新事件給所有工作器
            for worker_id in range(1, self.num_workers + 1):
                worker_key = f'worker_{worker_id}_urls'
                self.redis_client.publish(f'{worker_key}_update', 'updated')
                logging.info(f"Published update for worker {worker_id}.")

        else:
            logging.error(f"請求失敗，狀態碼：{response.status_code}")

    def run(self):
        thread = threading.Thread(target=self.fetch_and_update_cameras)
        thread.start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    manager = CameraManager()
    manager.run()