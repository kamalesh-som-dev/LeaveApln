import logging
import time

class CustomFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = time.localtime(record.created)
        formatted_time = time.strftime('%Y-%m-%d %H:%M:%S', dt)
        return formatted_time

handler = logging.StreamHandler() 
formatter = CustomFormatter('%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
log.addHandler(handler)