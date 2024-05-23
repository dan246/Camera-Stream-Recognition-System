import redis
import os
import json

# 初始化 Redis 連線
def init_redis():
    redis_host = 'redis'
    redis_port = 6379
    return redis.Redis(host=redis_host, port=redis_port, db=0)

class CameraSnapFetcher:
    def __init__(self, redis_connection):
        self.redis = redis_connection

    def get_snap_by_url(self, camera_url):
        key = f"camera_{camera_url}_latest_frame"
        path = self.redis.lrange(key, -1, -1)
        if not path:
            return None
        path = path[0].decode('utf-8')
        if os.path.exists(path):
            return path
        return None

def get_all_camera_status(r):
    status = {}
    for key in r.keys("camera_*_status"):
        camera_id = key.decode().split('_')[1]
        if r.exists(f'camera_{camera_id}_status'):
            camera_status = r.get(f'camera_{camera_id}_status').decode()
            last_timestamp = r.get(f'camera_{camera_id}_last_timestamp').decode() if r.exists(f'camera_{camera_id}_last_timestamp') else "unknown"
            fps = r.get(f'camera_{camera_id}_fps').decode() if r.exists(f'camera_{camera_id}_fps') else "unknown"
            url = r.get(f'camera_{camera_id}_url').decode() if r.exists(f'camera_{camera_id}_url') else "unknown"
            latest_frame_path = r.get(f'camera_{camera_id}_latest_frame_path').decode() if r.exists(f'camera_{camera_id}_latest_frame_path') else "No image saved"
            try:
                cls_serialized = r.get(f'camera_{camera_id}_last_cls').decode('utf-8')
                cls = cls_serialized.split(',')
                id_serialized = r.get(f'camera_{camera_id}_last_id').decode('utf-8')
                id = id_serialized.split(',')
                xywh_serialized = r.get(f'camera_{camera_id}_last_xywh').decode('utf-8')
                xywh = json.loads(xywh_serialized)
            except:
                cls = []
                id = []
                xywh = []
            
            status[camera_id] = {
                "alive": camera_status,
                "last_image_timestamp": last_timestamp,
                "fps": fps,
                "url": url,
                "latest_frame_path": latest_frame_path,  # 新增圖片路徑
                "cls":cls,
                "xywh":xywh,
                "id":id
            }
    return status


def get_all_camera_lists(r):
    status = {}
    camera_status_keys = r.keys("camera_*_status")
    
    for key in camera_status_keys:
        key = key.decode()  # 確保將鍵轉換為字串
        camera_id = key.split('_')[1]
        url_key = f'camera_{camera_id}_url'
        url = r.get(url_key).decode() if r.exists(url_key) else "unknown"
        
        status[camera_id] = {
            "url": url,
        }
    
    # 獲取所有可能存在的攝影機 URL
    camera_url_keys = r.keys("camera_*_url")
    
    for key in camera_url_keys:
        key = key.decode()  # 確保將鍵轉換為字串
        camera_id = key.split('_')[1]
        if camera_id not in status:
            url = r.get(key).decode() if r.exists(key) else "unknown"
            status[camera_id] = {
                "url": url,
            }
    
    # 過濾掉 URL 為 "unknown" 的項目
    filtered_status = {camera_id: info for camera_id, info in status.items() if info["url"] != "unknown"}
    
    return filtered_status
