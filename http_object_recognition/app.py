import logging
import asyncio
import numpy as np
import cv2
import time
import aiohttp
import datetime
from YOLOModel import YOLOModel
from RaiAPI import RaiAPI
from EventTracker import EventTracker
import os

# 初始化日誌設定
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    filename='app.log',
                    filemode='a')  # 'a' 表示附加模式，日誌會被添加到文件末尾

message_logger = logging.getLogger('MessageLogger')
message_handler = logging.FileHandler('message.log')
exception_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
message_handler.setFormatter(exception_formatter)
message_logger.addHandler(message_handler)
message_logger.setLevel(logging.INFO)


# 模型 URL
API_USER = os.getenv("API_USER", "your_API_USER")
API_PASSWORD = os.getenv("API_PASSWORD", "your_API_PASSWORD")
CAMERA_SERVICE_URL = os.getenv("CAMERA_SERVICE_URL", "your_CAMERA_SERVICE_URL")
# 初始化 YOLO 模型
firesmokeryolo = YOLOModel(os.getenv("FIRESMOKER_MODEL_URL", "your_model"))
fallyolo = YOLOModel(os.getenv("FALL_MODEL_URL", "your_model"))
wateryolo = YOLOModel(os.getenv("WATER_MODEL_URL", "your_model"))

# 事件追蹤器
eventtracker = EventTracker()

# API 設定


# Rai API 實例化並登入
mRaiAPI = RaiAPI(base_url=f"{CAMERA_SERVICE_URL}:7000")
mRaiAPI.login(API_USER, API_PASSWORD)

# 相機服務 URL
CAMERA_SERVICE_URL = f"{CAMERA_SERVICE_URL}:15439"

# 輪詢間隔時間
SLEEP_INTERVAL = 1  # seconds

async def fetch_camera_status(session):
    try:
        async with session.get(f"{CAMERA_SERVICE_URL}/camera_status") as response:
            if response.status == 200:
                return await response.json()
            return {}
    except Exception as e:
        logging.error(f"Error fetching camera status: {str(e)}")
        return {}

async def fetch_snapshot(session, camera_id):
    async with session.get(f"{CAMERA_SERVICE_URL}/get_snapshot/{camera_id}") as response:
        if response.status == 200:
            return await response.read()  # returns the image data as bytes
        return None

def create_image_grid(images, rows, cols):
    max_height = max(image.shape[0] for image in images)
    max_width = max(image.shape[1] for image in images)
    grid_image = np.zeros((max_height * rows, max_width * cols, 3), dtype=np.uint8)
    for idx, image in enumerate(images):
        if idx >= rows * cols:
            break
        row = idx // cols
        col = idx % cols
        grid_image[row*max_height:(row+1)*max_height, col*max_width:(col+1)*max_width, :image.shape[2]] = cv2.resize(image, (max_width, max_height))
    return grid_image

def call_model(imagesid, images, camera_id, type, camera_list_by_id):
    notify_message = {
        "firesmoker": "火焰通報請注意",
        "fall": "偵測到跌倒",
        "water": "偵測到淹水"
    }
    
    pairs = [(id, img) for id, img in zip(imagesid, images) if id in camera_id]
    if pairs:
        imagesid, images = zip(*pairs)
    else:
        return [], [], []
    if type == "firesmoker":
        model = firesmokeryolo
    elif type == "fall":
        model = fallyolo
    elif type == "water":
        model = wateryolo
    logging.info(f"Processing {len(images)} images for {type} detection")
    data = model.predict(images)
    for id, infdata in zip(imagesid, data):
        logging.info(f"Camera {id} detected {len(infdata)} {type} objects.")
        
        for inf in infdata:
            camera_name = camera_list_by_id[id]['camera_name']
            # camera_url = camera_list_by_id[id]['camera_url']
            camera_url = f"/images?id={id}&time={(datetime.datetime.utcnow() + datetime.timedelta(hours=8)).timestamp()}"
            second = int(camera_list_by_id[id]['camera_seting']['second'])
            have_event = False
            for boxe in inf.boxes:
                for cls, conf in zip(boxe.cls, boxe.conf):
                    if conf < 0.1:
                        continue
                    have_event = True
                    inftype = model.model.names[int(cls)]
                    timestamp = time.time()
                    utc_datetime = datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc)
                    formatted_string = utc_datetime.strftime('%Y-%m-%d %H:%M:%S')
                    sec, description = eventtracker.get_event_duration(id)
                    if description == "異常":
                        message_logger.info(f"id:{id} 異常已持續{sec}秒 鏡頭設定為{second}秒觸發")
                        if sec > second:
                            logging.info("新增事件")
                            mRaiAPI.create_notify(id, formatted_string, notify_message[type], camera_name, "", camera_url, inftype)
                    elif description != "正常":
                        message_logger.info(f"建立異常事件id:{id}")
                        eventtracker.add_event(id, "異常")
            if not have_event:
                message_logger.info(f"建立正常事件id:{id} not have_event")
                eventtracker.add_event(id, "正常")
    return imagesid, images, data

async def main():
    async with aiohttp.ClientSession() as session:
        last_timestamps = {}
        show_image_list = {}
        while True:
            starttime = time.time()
            logging.info("Checking cameras...")
            images, imagesid = [], []
            
            camera_list = mRaiAPI.get_camera_list()
            camera_list_by_id = {camera['camera_id']: camera for camera in camera_list}
            firesmoker_camera_id, fall_camera_id, water_camera_id = [], [], []
            for camera in camera_list:
                if camera['camera_seting']['item'] == "火焰煙霧":
                    firesmoker_camera_id.append(camera['camera_id'])
                elif camera['camera_seting']['item'] == "民眾路倒":
                    fall_camera_id.append(camera['camera_id'])
                elif camera['camera_seting']['item'] == "淹水偵測":
                    water_camera_id.append(camera['camera_id'])
            camera_status = await fetch_camera_status(session)
            for camera_id, status in camera_status.items():
                if status['alive'] and status['last_image_timestamp'] and \
                        (camera_id not in last_timestamps or status['last_image_timestamp'] != last_timestamps[camera_id]):
                    image_data = await fetch_snapshot(session, camera_id)
                    if image_data:
                        np_arr = np.frombuffer(image_data, np.uint8)
                        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                        if img is not None:
                            images.append(img)
                            imagesid.append(int(camera_id))
                            show_image_list[int(camera_id)] = img
                            logging.info(f"Image from camera {camera_id} ready for processing")
                            last_timestamps[camera_id] = status['last_image_timestamp']
                else:
                    logging.info(f"Camera {camera_id} is not alive or no new image")
            call_model(imagesid, images, firesmoker_camera_id, "firesmoker", camera_list_by_id)
            call_model(imagesid, images, fall_camera_id, "fall", camera_list_by_id)
            call_model(imagesid, images, water_camera_id, "water", camera_list_by_id)
            # 計算間隔，若低於 SLEEP_INTERVAL 則等待 達到 SLEEP_INTERVAL 時再繼續
            endtime = time.time()
            interval = endtime - starttime
            if interval < SLEEP_INTERVAL:
                await asyncio.sleep(SLEEP_INTERVAL - interval)
    #         # 取出show_image_list 中所有的image 放入 show_img中
    #         if len(list(show_image_list.keys())) > 0:
    #             show_img = [show_image_list[id] for id in list(show_image_list.keys())]
    #             if show_img:
    #                 rows, cols = 3, 3
    #                 grid_image = create_image_grid(show_img, rows, cols)
    #                 cv2.imshow('Camera Grid', grid_image)
    #                 if cv2.waitKey(1) & 0xFF == ord('q'):
    #                     break
    #             time.sleep(SLEEP_INTERVAL)
    # cv2.destroyAllWindows()

if __name__ == "__main__":
    asyncio.run(main())
