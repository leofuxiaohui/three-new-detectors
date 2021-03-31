class MockLogger:
    def __init__(self):
        self.info_list = []
        self.warning_list = []
        self.debug_list = []
        self.error_list = []

    def info(self, message: str) -> None:
        self.info_list.append(message)

    def warning(self, message: str) -> None:
        self.warning_list.append(message)

    def debug(self, message: str) -> None:
        self.debug_list.append(message)

    def error(self, message: str) -> None:
        self.error_list.append(message)
