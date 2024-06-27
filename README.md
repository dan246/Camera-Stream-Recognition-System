# Camera-Stream-Recognition-System
攝影機串流辨識系統

[中文版本](https://github.com/dan246/Camera-Stream-Recognition-System/blob/main/README.md)

支援 RTSP & HTTP

這個專案使用 Python 和 Redis，實現對多個攝影機串流的管理和辨識功能。主要功能包括攝影機串流的實時捕獲、物件辨識、圖像保存、ReID（再辨識）以及串流地址的動態更新。

可同時處理超過 100 台攝影機串流。Redis 會將功能平均分配到其他工作器上，所以如果感覺慢或運行不順暢，可以增加 worker 數量，並修改 camera_100 裡的 camera_manager（可以考慮在 Docker Compose 中設置環境變數動態調整）。

可以加入在docker裡加入 GPU 避免 CPU 滿載
```bash
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```
## 功能

- **串流獲取**：從多個攝影機連續取得串流圖像。
- **物件辨識**：利用深度學習模型對捕獲的圖像進行物件辨識（如車牌、異常行為如跌倒或暴力行為）。
- **再辨識（ReID）**: 基於物件辨識的結果進行個體再辨識，用於追蹤特定目標。
- **影片回放**：根據需求提供影片回放功能。
- **數據存檔**：將取得的圖像存儲到本地系統並同步路徑資料到 Redis。
- **動態更新**：可動態更新攝影機串流列表，並通過 Redis 實現多個工作節點間的同步。



## 開始

以下是本地環境部署和運行本系統的步驟。

### 環境

- Docker
- Docker Compose
- Python 3.8 或更高版本
- GPU

### 安裝

1. **克隆專案**

   ```bash
   git clone https://github.com/yourgithub/camera-stream-handler.git
   cd camera-stream-handler

2.  **使用 Docker Compose 來構件和啟動系統**
   ```bash
   docker-compose -f docker-compose-deploy.yaml -f docker-compose-redis.yaml build
   docker-compose -f docker-compose-deploy.yaml -f docker-compose-redis.yaml up -d
  ```

### API文檔
API 文檔可通過以下地址查看：
   ```bash
   localhost:15439
   ```


### 注意事項

1. **docker-comose 文件可依照其他需求新建其他容器**

  例如，數據庫（DB）、前端 Web、Nginx 等等。這裡的配置主要包括後端和部分網頁(截圖)，大部分功能需通過 API 交流。


2. **啟動後再執行 addw1(有 DB 則在 camera_ctrler 裡的 camera_manager 設定連線方式)，也可以透過API文檔裡的 API 直接設定**

   如果沒有 DB，由於 Redis 啟動後還沒註冊事件，需要啟動後從API文檔裡的 API 設定攝影機

3. **(資料源為DB) Redis 攝影機輸入的資料為 id + camera_url，如果是使用 API 則會自動建 id**

4. **圖片會生成於 Redis 底下的 frames 資料夾中**

   frames 同時會掛載到 camera_ctrler 取截圖與串流回放

5. **模型請自行載入，目前這裡暫不提供**


### 未來拓展與優化

*** 系統性能優化 ***
1. 水平擴展：
   - 增加更多的工作節點，以分散和處理更多的攝影機串流。
   - 使用 Kubernetes 或其他容器編排工具來動態調整工作節點的數量。

2. 負載均衡：
   - 引入負載均衡器來分配攝影機串流和工作負載。
   - 使用 Nginx 或 HAProxy 等工具來實現負載均衡。

3. 硬件加速：
   - 更多使用 GPU 來加速物件辨識和 ReID 任務。
   - 使用 CUDA 和 cuDNN 來進一步優化深度學習模型的推理速度。

*** 功能拓展 ***
1. 更多物件辨識模型：
   - 引入更多種類的物件辨識模型，例如人臉辨識、車輛辨識等。
   - 支持多模型並行運行，根據不同場景選擇合適的模型。

2. 智能事件檢測：
   - 增加智能事件檢測功能，例如人群聚集、火災偵測等。
   - 使用複合事件處理技術來實現複雜場景下的事件檢測。

3. 圖像增強與預處理：
   - 增加圖像增強技術，提高低光照、模糊等條件下的辨識準確率。
   - 引入圖像預處理模塊，提高辨識模型的輸入質量。

*** 系統可靠性與安全性 ***
1. 數據備份與恢復：
   - 引入數據備份機制，定期備份 Redis 和本地存儲的圖像數據。
   - 提供數據恢復功能，保障系統故障時數據不丟失。

2. 安全性增強：
   - 增加攝影機串流和 API 的安全認證機制。
   - 使用 HTTPS 保護數據傳輸安全。

*** 用戶體驗與界面優化 ***
1. 友好的用戶界面：
   - 提供更直觀和友好的前端界面，便於用戶管理攝影機和查看辨識結果。
   - 使用現代前端框架（如 React、Vue.js）來構建動態響應式界面。

2. 自動報告與通知：
   - 增加自動報告生成功能，定期生成攝影機運行狀態和辨識結果報告。
   - 提供即時通知功能，當偵測到異常事件時，通過郵件、短信等方式通知用戶。


*** 技術堆棧與架構改進 ***
1. 微服務架構：
   - 將系統拆分為微服務，每個功能模塊作為獨立的服務運行，提升系統的可維護性和擴展性。
   - 使用 API Gateway 管理各個微服務的統一入口。

2. 數據庫優化：
   - 引入 NoSQL 數據庫（如 MongoDB）存儲結構化數據，提高數據存取性能。
   - 使用數據庫分片技術來分散數據存儲，提升系統的可擴展性。

*** 深度學習與AI模型改進 ***
1. 模型訓練與調優：
   - 針對不同場景和需求，訓練和調優專門的深度學習模型。
   - 使用自動化機器學習技術（如 AutoML）提高模型的性能和準確性。

2. 在線學習：
   - 實現在線學習功能，系統在運行過程中根據新數據動態更新模型。
   - 使用遷移學習技術，基於已有模型快速適應新的場景。
