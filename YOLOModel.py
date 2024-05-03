import os
import hashlib
from urllib import request
from pathlib import Path
from ultralytics import YOLO

class YOLOModel:
    def __init__(self, model_url):
        self.model_url = model_url
        self.model_path = self._download_model()
        self.model = self._load_model()

    def _download_model(self):
        # 創建存儲模型的臨時目錄
        tmp_dir = Path("tmp")
        tmp_dir.mkdir(exist_ok=True)

        # 通過 URL 生成唯一的文件名
        filename = hashlib.md5(self.model_url.encode('utf-8')).hexdigest() + ".pt"
        file_path = tmp_dir / filename

        # 如果文件不存在，則下載
        if not file_path.exists():
            print("下載模型...")
            request.urlretrieve(self.model_url, file_path)
        else:
            print("模型已存在，不需重新下載。")

        return file_path

    def _load_model(self):
        # 加載模型
        print("載入模型...")
        return YOLO(self.model_path)

    def predict(self, image_path):
        # 進行推論
        data = self.model(image_path)
        return data
    

    