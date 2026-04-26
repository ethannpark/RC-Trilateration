import serial
import json
import numpy as np
import re

# must set two/three dimensional and location (x,y,z) of all used tags
# 2d should only set x, y coords (z ignored)
two_dimensional = True
three_dimensional = False

# 115200
        

anchor_id = "0xdecaab9874a55a0d"

tag_ids = "0xdeca7aa6ee520423", "0xdecaf1a1b2e24487", "0xdeca7aab4d42488f", "0xdecabcef96d20924"
# x, y, z, dist
# all measurements in mm
tag_data = {
    "0x0423": [0,0,0,-1],
    "0x4487": [0,0,0,-1],
    "0x488f": [0,0,0,-1],
    "0x0924": [0,0,0,-1]
}
serial_port = '/dev/ttyUSB0'

smoothing_alpha = .35


def trilaterate3D_least_squares(distances):
    # distances = [(x, y, z, r), ...]
    p1 = np.array(distances[0][:3])
    r1 = distances[0][3]
    A = []
    b = []

    for d in distances[1:]:
        pi = np.array(d[:3])
        ri = d[3]
        A.append(2 * (pi - p1))
        b.append(
            r1**2 - ri**2 +
            np.dot(pi, pi) -
            np.dot(p1, p1)
        )

    A = np.array(A)
    b = np.array(b)
    # Solve least squares
    x, residuals, rank, s = np.linalg.lstsq(A, b, rcond=None)
    return x
    
def trilaterate2D_least_squares(distances):
    # distances = [(x, y, r), ...]
    p1 = np.array(distances[0][:2])
    r1 = distances[0][2]
    A = []
    b = []
    
    for d in distances[1:]:
        pi = np.array(d[:2])
        ri = d[2]
        
        A.append(2 * (pi - p1))
        
        b.append(
            r1**2 - ri**2 +
            np.dot(pi, pi) -
            np.dot(p1, p1)
        )

    A = np.array(A)
    b = np.array(b)
    x, residuals, rank, s = np.linalg.lstsq(A, b, rcond=None)
    return x

# parse distance received via regex, only taking registered anchors, and apply exponential smoothing
def parse_distances(line):

    pattern = r"(0x[0-9A-Fa-f]+):=(\d+)"
    matches = re.findall(pattern, line)

    for anchor, dist in matches:
        if anchor in tag_data:
            if tag_data[anchor][3] != -1:
                tag_data[anchor][3] = int(dist) * smoothing_alpha + (1-smoothing_alpha) * tag_data[anchor][3]
            else:
                tag_data[anchor][3] = int(dist)


def dict_to_array(tag_data):
    pts = []

    for anchor, values in tag_data.items():
        # only include valid distances, cannot be directly on top of
        if values[3] > 0: 
            pts.append(values)

    return pts


def read_serial_trilaterate(on_position=None):
    ser = serial.Serial(serial_port, 115200, timeout=1)
    while True:
        line = ser.readline().decode(errors='ignore').strip()
        if not line:
            continue

        parse_distances(line)
        pts = dict_to_array(tag_data)
        pos = None

        if (two_dimensional and len(pts) >= 3):
            pts2d = [[p[0], p[1], p[3]] for p in pts]
            pos = trilaterate2D_least_squares(pts2d)
            print("2D Position:", pos)
        elif len(pts) >= 4:
            pos = trilaterate3D_least_squares(pts[:4])
            print("3D Position:", pos)
        
        if pos is not None:
            if on_position:
                on_position(pos)

def start_trilateration(on_position):
    thread = threading.Thread(
        target=read_serial_trilaterate,
        args=(on_position,),
        daemon=True
    )
    thread.start()

        
