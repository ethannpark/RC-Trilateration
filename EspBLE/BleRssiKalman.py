import asyncio
from bleak import BleakScanner
import math

Beacon_Names = {
    "A4537458-85AD-11DF-23F8-A025E6981BA0", #B1
    "10C8CE33-CAF8-0964-BCAE-6797E678C0FC", #B2
    "E03E25A9-9932-417A-4742-88FEF1956C1E"  #B3
}

class KalmanFilter:
    def __init__(self, process_variance=1e-3, measurement_variance=1):
        self.process_variance = process_variance
        self.measurement_variance = measurement_variance
        self.estimate = None
        self.error = 1.0

    def update(self, measurement):
        if self.estimate is None:
            self.estimate = measurement

        # Prediction update
        self.error += self.process_variance

        # Measurement update
        kalman_gain = self.error / (self.error + self.measurement_variance)
        self.estimate += kalman_gain * (measurement - self.estimate)
        self.error *= (1 - kalman_gain)

        return self.estimate
    
class Circle:
    def __init__(self, id, x, y, radius):
        self.id = id
        self.x = x
        self.y = y
        self.radius = radius

#https://rodstephensbooks.com/trilateration.html
def find_circle_circle_intersections(center0, radius0, center1, radius1):
    '''Find the 0, 1, or 2 points where the circles intersect.'''
    # Find the distance between the centers.
    dx = center0[0] - center1[0]
    dy = center0[1] - center1[1]
    dist = math.sqrt(dx * dx + dy * dy)

    # See if the circles are so far apart they don't intersect.
    if dist > radius0 + radius1:
        # print('Circles too far apart, no intersections')
        return ()

    # See if one circle contains the other.
    if dist < abs(radius0 - radius1):
        # print('One circle inside the other, no intersections')
        return ()

    # See if the circles coincide.
    if math.isclose(dist, 0) and math.isclose(radius0, radius1):
        # print('Circles coincide, no intersections')
        return ()

    # Otherwise we have 1 or 2 intersections.
    # Find a and h.
    a = (radius0 * radius0 - radius1 * radius1 + dist * dist) / (2 * dist)
    h = math.sqrt(radius0 * radius0 - a * a)

    # Find P2.
    cx2 = center0[0] + a * (center1[0] - center0[0]) / dist
    cy2 = center0[1] + a * (center1[1] - center0[1]) / dist

    # Get the points P3.
    intersection1 = (
        cx2 + h * (center1[1] - center0[1]) / dist,
        cy2 - h * (center1[0] - center0[0]) / dist)
    intersection2 = (
        cx2 - h * (center1[1] - center0[1]) / dist,
        cy2 + h * (center1[0] - center0[0]) / dist)

    # See if we have 1 or 2 solutions.
    # print(f'{intersection1 = }')
    # print(f'{intersection2 = }')
    if math.isclose(intersection1[0], intersection2[0]) and \
            math.isclose(intersection1[1], intersection2[1]):
        # One intersection. They're the same point.
        return (intersection1,)
    return (intersection1, intersection2)

def trilaterate(circle1, circle2, circle3):
    '''Perform the trilateration.'''
    # Find the points of intersection.
    p12 = find_trilateralization_corner(circle1, circle2, circle3)
    p23 = find_trilateralization_corner(circle2, circle3, circle1)
    p31 = find_trilateralization_corner(circle3, circle1, circle2)
    if p12 is None or p23 is None or p31 is None:
        return None
    return (p12, p23, p31)

def find_trilateralization_corner(c1, c2, c3):
    '''
    Find the intersections between circles c1 and c2.
    Return the point of intersection (POI) closest to the center of c3.
    '''
    intersections = find_circle_circle_intersections(
        (c1.x, c1.y), c1.radius,
        (c2.x, c2.y), c2.radius)
    
    if not intersections:
        return None

    distances = [euclidean_distance(point[0], point[1], c3.x, c3.y)
                 for point in intersections]
    min_distance = min(distances)
    index = distances.index(min_distance)
    return intersections[index]

def find_triangle_centroid(p1, p2, p3):
    '''Return the triangle's centroid.'''
    return (
        (p1[0] + p2[0] + p3[0]) / 3,
        (p1[1] + p2[1] + p3[1]) / 3
    )
    
# beacon locations currently set at 0,0, 3,0, 0,3 all in meters
BEACONS = {
    "A4537458-85AD-11DF-23F8-A025E6981BA0": {"circle": Circle("B1", 0, 0, None), "kf": KalmanFilter()}, #B1
    "10C8CE33-CAF8-0964-BCAE-6797E678C0FC": {"circle": Circle("B2", 3, 0, None), "kf": KalmanFilter()}, #B2
    "E03E25A9-9932-417A-4742-88FEF1956C1E": {"circle": Circle("B3", 0, 3, None), "kf": KalmanFilter()}, #B3
}

# ~-70 transmit power at ~1 meter
def rssi_distance(rssi):
    tx_power = -70 # -69.425 
    return 10 ** ((tx_power-rssi)/(10*2))

def euclidean_distance(x1, y1, x2, y2):
    return math.sqrt((x1-x2)**2 + (y1-y2)**2)

def detection_callback(device, adv_data):
    if device.address in BEACONS:
        beacon = BEACONS[device.address]
        raw_rssi = adv_data.rssi
        smooth_rssi = beacon["kf"].update(raw_rssi)

        dist = rssi_distance(smooth_rssi)
        beacon["circle"].radius = dist

        print(f"{device.name}: {dist:.2f}m")
        if all(b["circle"].radius is not None for b in BEACONS.values()):
            b1 = BEACONS["A4537458-85AD-11DF-23F8-A025E6981BA0"]
            b2 = BEACONS["10C8CE33-CAF8-0964-BCAE-6797E678C0FC"]
            b3 = BEACONS["E03E25A9-9932-417A-4742-88FEF1956C1E"]
            c1 = b1["circle"]
            c2 = b2["circle"]
            c3 = b3["circle"]
            result = trilaterate(c1, c2, c3)
            if result:
                p1, p2, p3 = result
                centroid = find_triangle_centroid(p1, p2, p3)
                print(f"Location: {centroid}") # best guess of location

        print("-" * 20)


async def main():
    scanner = BleakScanner(detection_callback)
    await scanner.start()

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Stopping scanner...")
        await scanner.stop()

asyncio.run(main())


TARGET = "A4537458-85AD-11DF-23F8-A025E6981BA0"

# measure RSSI of beacon over time at 1 meter away
async def measure_rssi():
    samples = []
    n = 1
    for _ in range(40):  # collect multiple readings
        devices = await BleakScanner.discover(return_adv=True)
        print(n)
        n += 1
        for addr, (device, adv) in devices.items():
            if addr == TARGET:
                samples.append(adv.rssi)

        await asyncio.sleep(0.2)

    if samples:
        avg_rssi = sum(samples) / len(samples)
        print(f"Estimated tx_power (RSSI @1m): {avg_rssi}")

# asyncio.run(measure_rssi())
