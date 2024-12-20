import logging

class LogCaptureHandler(logging.Handler):
    """
    Кастомный обработчик логов для захвата логов в память.
    """
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(self.format(record))

    def get_logs(self):
        return "\n".join(self.records)
