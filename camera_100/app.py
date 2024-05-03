from flask import Flask, request, send_file, jsonify, render_template,Response
from flask_restx import Api, Resource, fields, abort
from camera_manager import CameraManager
import cv2
import numpy as np
import io
import pandas as pd
from flask import current_app
import csv
from threading import Thread
import time
from time_stamped_images import TimeStampedImages
import redis
import os
from PIL import Image, ImageDraw
import threading
import base64   


app = Flask(__name__)
# api = Api(app,doc=False)

api = Api(app)

def setup_camera_manager():
    manager = CameraManager()
    manager.run()
    # 設定 Timer 來周期性檢查攝影機更新，每 1 秒執行一次
    timer = threading.Timer(1, setup_camera_manager)  # 重新設定 Timer
    timer.start()

setup_camera_manager()

# 定義模型
camera_model = api.model('Camera', {
    'camera_id': fields.String(required=True, description='The camera identifier'),
    'url': fields.String(required=True, description='The URL of the camera stream')
})

camera_ids_model = api.model('CameraIds', {
    'camera_ids': fields.List(fields.String, required=True, description='List of camera identifiers')
})

rect_model = api.model('Rectangle', {
    'x': fields.Float(required=True, description='X coordinate of the rectangle'),
    'y': fields.Float(required=True, description='Y coordinate of the rectangle'),
    'width': fields.Float(required=True, description='Width of the rectangle'),
    'height': fields.Float(required=True, description='Height of the rectangle'),
    'camera_id': fields.String(required=True, description='Camera ID associated with this rectangle')
})

# 初始化 Redis 連線
redis_host = 'redis'
redis_port = 6379
r = redis.Redis(host=redis_host, port=redis_port, db=0)

class CameraSnapFetcher:
    def __init__(self, redis_connection):
        self.redis = redis_connection

    def get_snap_by_url(self, camera_url):
        """根據攝影機 URL 從 Redis 獲取最新的圖片路徑"""
        # 構造查找的 key
        key = f"camera_{camera_url}_latest_frame"
        # 從該 key 的 list 中獲取最後一個元素（最新的圖片）
        path = self.redis.lrange(key, -1, -1)
        if not path:
            return None
        # 確保文件存在
        path = path[0].decode('utf-8')
        if os.path.exists(path):
            return path
        return None


def get_all_camera_status():
    status = {}
    for key in r.keys("camera_*_status"):
        camera_id = key.decode().split('_')[1]
        # 檢查攝像頭的狀態是否存在
        if r.exists(f'camera_{camera_id}_status'):
            camera_status = r.get(key)
            last_timestamp = r.get(f'camera_{camera_id}_last_timestamp')
            # 確認取得的資料不為 None 再進行 decode
            if camera_status is not None and last_timestamp is not None:
                camera_status = camera_status.decode()
                last_timestamp = last_timestamp.decode()
                status[camera_id] = {
                    "alive": camera_status,
                    "last_image_timestamp": last_timestamp
                }
            else:
                # 對於找不到的鍵值，可以設定一個預設值或記錄錯誤
                status[camera_id] = {
                    "alive": "unknown",
                    "last_image_timestamp": "unknown"
                }
    return status


@api.route('/camera_status')
class CameraStatus(Resource):
    def get(self):
        status = get_all_camera_status()
        return status, 200


@app.route('/get_snapshot/<camera_id>')
def get_latest_frame(camera_id):
    """提供指定攝影機的最新圖像"""
    image_data = r.get(f'camera_{camera_id}_latest_frame')
    if image_data:
        return Response(image_data, mimetype='image/jpeg')
    else:
        return "No image found", 404

def generate_frames(camera_id):
    while True:
        frame_key = f'camera_{camera_id}_latest_frame'
        frame_data = r.get(frame_key)
        if frame_data:
            yield (b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')  # 構造串流框架
        time.sleep(0.1)


@app.route('/get_stream/<int:ID>')
def get_stream(ID):
    return Response(generate_frames(ID),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/snapshot_ui/<ID>')
def snapshot_ui(ID):
    image_key = f'camera_{ID}_latest_frame'
    image_data = r.get(image_key)
    if image_data:
        # 將繪製了矩形的圖像轉為 base64 編碼
        image = Image.open(io.BytesIO(image_data))
        draw = ImageDraw.Draw(image)

        # 從 Redis 獲取該 ID 的所有矩形並繪製它們
        rects_key = f'rectangles_{ID}'
        for key in r.scan_iter(f"{rects_key}:*"):
            rect_data = r.hgetall(key)
            rect = [int(float(v.decode())) for v in rect_data.values()]
            draw.rectangle(rect, outline='red', width=2)

        # 保存更新後的圖像
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        encoded_image = base64.b64encode(buffered.getvalue()).decode('utf-8')

        return render_template('snapshot_ui.html', camera_id=ID, image_data=encoded_image)
    else:
        return "No image available", 404

@app.route('/rectangles/<ID>', methods=['POST', 'GET', 'DELETE'])
def handle_rectangles(ID):
    # 確認 camera_id 是否存在
    camera_status = r.get(f'camera_{ID}_status')
    if camera_status is None:
        return jsonify(message="無效的 ID"), 404

    # 直接使用 ID 創建矩形鍵，而不是從圖像數據中解碼
    rects_key = f'rectangles_{ID}'

    if request.method == 'POST':
        rects = request.get_json()
        # 使用 hash 存儲每個矩形資料，並確保使用 str 儲存
        for idx, rect in enumerate(rects):
            r.hset(f"{rects_key}:{idx}", mapping={k: str(v) for k, v in rect.items()})
        return jsonify(message="矩形已儲存"), 200

    elif request.method == 'GET':
        rects = []
        # 掃描並解碼儲存在 Redis 中的矩形資料
        for key in r.scan_iter(f"{rects_key}:*"):
            rect_data = r.hgetall(key)
            rect = {k.decode(): int(float(v.decode())) for k, v in rect_data.items()}
            rects.append(rect)
        return jsonify(rects)

    elif request.method == 'DELETE':
        # 刪除所有矩形資料
        for key in r.scan_iter(f"{rects_key}:*"):
            r.delete(key)
        return jsonify(message="所有矩形已清除"), 200


# david 新增圖片輪播功能
def generate_image_stream(image_paths):
    while True:
        for image_path in image_paths:
            with open(image_path, 'rb') as image_file:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + image_file.read() + b'\r\n')
                time.sleep(1)
        if not image_paths:
            with open('no_single.jpg', 'rb') as image_file:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + image_file.read() + b'\r\n')
                time.sleep(1)

from datetime import datetime
@app.route('/images')
def images():
    folder_id = request.args.get('id', '0')
    folder_path = f'image/{folder_id}'
    
    # 將時間戳解碼成 datetime 物件，然後根據需求格式解碼
    time_str = request.args.get('time', '')
    try:
        # unix2utc
        current_time = datetime.utcfromtimestamp(float(time_str))
    except ValueError:
        # 如果時間格式不正確，返回預設值
        current_time = datetime.now()  # 或是返回一個錯誤

    # 計算開始和結束時間
    start_timestamp = current_time.timestamp() - 15
    end_timestamp = current_time.timestamp() + 15
    # folder_path=folder_path+'/'+current_time.strftime('%Y%m%d')
    tsi = TimeStampedImages(folder_path)
    image_paths = tsi.find_images_in_range(start_timestamp, end_timestamp)
    
    return Response(generate_image_stream(image_paths), mimetype='multipart/x-mixed-replace; boundary=frame')



if __name__ == '__main__':
    app.run()
