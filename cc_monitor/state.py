"""全局状态单例"""


class AppState:
    def __init__(self):
        self.api_key: str = ""
        self.rate_limiter = None
        self.guard = None
        self.device_tracker = None


app_state = AppState()
