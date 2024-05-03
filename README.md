# Camera-Stream-Recognition-System
攝影機串流辨識系統

這個專案使用 Python 和 Redis，實現對多個攝影機串流的管理和辨識功能。主要功能包括攝影機串流的實時捕獲、物件辨識、圖像保存以及串流地址的動態更新。


## 功能

- **串流捕獲**：從多個攝影機連續捕獲圖像。
- **物件辨識**：利用深度學習模型對捕獲的圖像進行物件辨識。
- **影片回放**：影片回放功能可依需求， 
- **數據存儲**：將捕獲的圖像存儲到本地系統並同步路徑信息到 Redis。
- **動態更新**：可動態更新攝影機串流列表，並通過 Redis 實現多個工作節點間的同步。

## 開始

以下將幫助你在本地環境上部署和運行本系統。

### 環境

- Docker
- Docker Compose
- Python 3.8 或更高版本

### 安裝

1. **克隆專案**

   ```bash
   git clone https://github.com/yourgithub/camera-stream-handler.git
   cd camera-stream-handler

2.  **使用 Docker Compose 來構件和啟動系統**
   ```bash
   docker-compose build
   docker-compose up -d
   ```

### 注意事項

1. **docker-comose 檔可依照其他需求新建其他 container**

   ex. DB、前台 web 等等


3. **啟動後再執行 addw1(有 DB 則在camera_100 裡的 camera_manager 設定連線方式)**

   如果沒有 DB，由於 redis 啟動後還沒註冊事件，所以啟動後需再執行 addw1.py 來註冊事件和分配容器

3. **redis 攝影機輸入的資料為 id + camera_url**

4. **圖片會生成於 redis 底下的 frames 資料夾中**

   frames 同時會掛載到 camera_100 取回放


持續修改中
