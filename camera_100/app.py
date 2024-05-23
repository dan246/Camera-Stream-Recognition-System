from flask import Flask, request, jsonify, send_file, render_template, Response
from flask_restx import Api, Resource, fields
from redis_utils import init_redis, CameraSnapFetcher, get_all_camera_status, get_all_camera_lists
# from camera_manager import CameraManager
from time_stamped_images import TimeStampedImages
import threading
import time
from datetime import datetime
from PIL import Image, ImageDraw
import base64
import io
import os
from datetime import datetime
app = Flask(__name__)
api = Api(app)

# 初始化 Redis
r = init_redis()

WORKER = os.getenv('WORKER')
# def setup_camera_manager():
#     manager = CameraManager()
#     manager.run()
#     timer = threading.Timer(1, setup_camera_manager)
#     timer.start()

# setup_camera_manager()

camera_model = api.model('Camera', {
    'camera_id': fields.String(required=True, description='The camera identifier'),
    'url': fields.String(required=True, description='The URL of the camera stream')
})

camera_ids_model = api.model('CameraIds', {
    'camera_ids': fields.List(fields.String, required=True, description='List of camera identifiers')
})

camera_urls_model = api.model('CameraUrlList', {
    'urls': fields.List(fields.String, required=True, description='List of camera URLs')
})

rect_model = api.model('Rectangle', {
    'x': fields.Float(required=True, description='X coordinate of the rectangle'),
    'y': fields.Float(required=True, description='Y coordinate of the rectangle'),
    'width': fields.Float(required=True, description='Width of the rectangle'),
    'height': fields.Float(required=True, description='Height of the rectangle'),
    'camera_id': fields.String(required=True, description='Camera ID associated with this rectangle')
})

@api.route('/camera_status')
class CameraStatus(Resource):
    def get(self):
        status = get_all_camera_status(r)
        return status, 200

@api.route('/get_camera_lists')
class CameraStatus(Resource):
    def get(self):
        status = get_all_camera_lists(r)
        return status, 200

@api.route('/set_camera_urls')
class SetCameraUrls(Resource):
    @api.expect(camera_urls_model)
    def post(self):
        data = request.get_json()
        camera_urls = data.get('urls', [])

        if not camera_urls:
            response = jsonify(message="No URLs provided.")
            response.status_code = 400
            return response

        # 清空 Redis 數據庫
        print("Flushing all Redis data")
        r.flushall()

        # 清空舊的攝影機列表
        for worker_id in range(1, 24):
            worker_key = f'worker_{worker_id}_urls'
            r.delete(worker_key)
            print(f"Deleted worker key: {worker_key}")

        # 分配新的攝影機到容器
        for count, url in enumerate(camera_urls):
            worker_id = (count % 23) + 1  # 工作器 ID
            worker_key = f'worker_{worker_id}_urls'
            result = r.sadd(worker_key, f'{count + 1}|{url}')  # 將攝影機 ID 從 1 開始
            if result == 1:
                print(f'Successfully added URL {url} to worker {worker_id}')
            else:
                print(f'Failed to add URL {url} to worker {worker_id}')
            # 新增 camera_*_url 鍵
            camera_key = f'camera_{count + 1}_url'  # 將攝影機 ID 從 1 開始
            r.set(camera_key, url)
            print(f'Set {camera_key} to {url}')

        # 發布更新事件給所有工作器
        for worker_id in range(1, 24):
            worker_key = f'worker_{worker_id}_urls'
            result = r.publish(f'{worker_key}_update', 'updated')
            print(f'Publishing update to worker {worker_id} with result: {result}')

        # 驗證所有的 key 和它們的值
        for worker_id in range(1, 24):
            worker_key = f'worker_{worker_id}_urls'
            urls = r.smembers(worker_key)
            print(f'Worker {worker_id} has URLs: {urls}')

        response = jsonify(message="Camera URLs have been successfully added and distributed to workers.")
        response.status_code = 200
        return response

# @app.route('/get_snapshot/<camera_id>')
# def get_latest_frame(camera_id):
#     image_data = r.get(f'camera_{camera_id}_latest_frame')
#     if image_data:
#         return Response(image_data, mimetype='image/jpeg')
#     else:
#         return send_file('no_single.jpg', mimetype='image/jpeg')
#         # return "No image found", 404

@api.route('/get_snapshot/<string:camera_id>')
class GetSnapshot(Resource):
    def get(self, camera_id):
        image_data = r.get(f'camera_{camera_id}_latest_frame')
        if image_data:
            return Response(image_data, mimetype='image/jpeg')
        else:
            return send_file('no_single.jpg', mimetype='image/jpeg')

def generate_frames(camera_id):
    while True:
        frame_key = f'camera_{camera_id}_latest_frame'
        frame_data = r.get(frame_key)
        if frame_data:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
        time.sleep(0.1)

@app.route('/get_stream/<int:ID>')
def get_stream(ID):
    return Response(generate_frames(ID), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/snapshot_ui/<ID>')
def snapshot_ui(ID):
    image_key = f'camera_{ID}_latest_frame'
    image_data = r.get(image_key)
    if image_data:
        image = Image.open(io.BytesIO(image_data))
        draw = ImageDraw.Draw(image)
        rects_key = f'rectangles_{ID}'
        for key in r.scan_iter(f"{rects_key}:*"):
            rect_data = r.hgetall(key)
            rect = [int(float(v.decode())) for v in rect_data.values()]
            # 確保 x1 >= x0 和 y1 >= y0
            if rect[2] < 0:  # rect[2] 是 width，如果是負數，需要調整 x 與 width
                rect[0] += rect[2]  # rect[0] 是 x
                rect[2] = abs(rect[2])
            if rect[3] < 0:  # rect[3] 是 height，如果是負數，需要調整 y 與 height
                rect[1] += rect[3]  # rect[1] 是 y
                rect[3] = abs(rect[3])
            draw.rectangle([rect[0], rect[1], rect[0] + rect[2], rect[1] + rect[3]], outline='red', width=2)
        
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        encoded_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
        return render_template('snapshot_ui.html', camera_id=ID, image_data=encoded_image)
    else:
        return send_file('no_single.jpg', mimetype='image/jpeg')
        # return "No image available", 404

@app.route('/rectangles/<ID>', methods=['POST', 'GET', 'DELETE'])
def handle_rectangles(ID):
    camera_status = r.get(f'camera_{ID}_status')
    if camera_status is None:
        return jsonify(message="無效的 ID"), 404
    rects_key = f'rectangles_{ID}'
    if request.method == 'POST':
        rects = request.get_json()
        for idx, rect in enumerate(rects):
            r.hset(f"{rects_key}:{idx}", mapping={k: str(v) for k, v in rect.items()})
        return jsonify(message="矩形已儲存"), 200
    elif request.method == 'GET':
        rects = []
        for key in r.scan_iter(f"{rects_key}:*"):
            rect_data = r.hgetall(key)
            rect = {k.decode(): int(float(v.decode())) for k, v in rect_data.items()}
            rects.append(rect)
        return jsonify(rects)
    elif request.method == 'DELETE':
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


@app.route('/images')
def images():
    folder_id = request.args.get('id', '0')
    folder_path = f'image/{folder_id}'
    
    # 將時間戳參數解析成 datetime 物件，然後根據需求格式解析
    time_str = request.args.get('time', '')
    try:
        # 假設時間參數是 '20240503145947' 這種格式
        current_time = datetime.utcfromtimestamp(float(time_str))
    except ValueError:
        # 如果時間格式不正確，可以設置一個預設值或返回錯誤
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



if __name__ == '__main__':
    app.run()
