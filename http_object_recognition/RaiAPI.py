import requests

class RaiAPI:
    def __init__(self, base_url):
        self.base_url = base_url
        self.access_token = ""
        self.refresh_token = ""

    def login(self, account, password):
        url = f'{self.base_url}/api/1/user/login'
        payload = {
            "account": account,
            "password": password
        }
        headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json'
        }
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            self.access_token = data.get('access_token')
            self.refresh_token = data.get('refresh_token')
            return True
        return False

    def create_notify(self, camera_id, alert_time, text, camera_name, ip, picture_url, notify_type):
        if not self.access_token:
            print("Please login first.")
            return False
        url = f'{self.base_url}/api/1/camera/create_notify'
        data = {
            "camera_id": camera_id,
            "alert_time": alert_time,
            "text": text,
            "camera_name": camera_name,
            "ip": ip,
            "picture_url": picture_url,
            "type": notify_type
        }
        headers = {
            'accept': 'application/json',
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        response = requests.post(url, data=data, headers=headers)
        return response.json()
    
    def get_camera_list(self):
        if not self.access_token:
            print("Please login first.")
            return False
        url = f'{self.base_url}/api/1/camera/get_camera_list'
        headers = {
            'accept': 'application/json',
            'Authorization': f'Bearer {self.access_token}'
        }
        response = requests.get(url, headers=headers)
        data = response.json()
        cameralist = []
        if 'data' in data:
            for camera in data['data']:
                if camera['camera_url'] is not None:
                    cameralist.append(camera)
        return cameralist
