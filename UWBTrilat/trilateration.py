from UartReader import start_trilateration
import time

latest_position = None

def get_position(pos):
    global latest_position
    latest_position = pos.tolist() if hasattr(pos, "tolist") else pos
    print("New position:", latest_position)

start_trilateration(get_position)

while True:
    time.sleep(1)