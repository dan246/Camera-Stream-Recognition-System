import datetime

class EventTracker:
    def __init__(self):
        # 初始化一個字典來存儲事件和它們的開始時間
        self.events = {}
    
    def add_event(self, event_id, event_description):
        """
        添加一個事件和它的 ID，自動記錄當前時間作為事件開始時間。
        """
        self.events[event_id] = {
            'description': event_description,
            'start_time': datetime.datetime.now(datetime.timezone.utc)
        }
    
    def get_event_duration(self, event_id):
        """
        根據事件的 ID 計算從事件開始到現在的持續時間（返回時間差的秒數）。
        """
        if event_id in self.events:
            current_time = datetime.datetime.now(datetime.timezone.utc)
            start_time = self.events[event_id]['start_time']
            duration = current_time - start_time
            return duration.total_seconds(),self.events[event_id]['description']
        else:
            return None,None  # 如果沒有找到事件 ID，返回 None


