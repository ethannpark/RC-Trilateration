from flask import Flask, Response, render_template_string, request, jsonify
import cv2
import threading

from UWBTrilat.UartReader import start_trilateration

app = Flask(__name__)

camera = cv2.VideoCapture(0)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

current_direction = "stop"
latest_position = None
position_lock = threading.Lock()

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RC Live Camera Feed</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background: #111;
            color: white;
            text-align: center;
            padding: 2rem;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
        }
        img {
            width: 100%;
            max-width: 800px;
            border-radius: 12px;
            border: 2px solid #444;
        }
        .status {
            margin-top: 1rem;
            font-size: 1.1rem;
            color: #bbb;
        }
        .controls {
            margin-top: 1.5rem;
            color: #ddd;
            font-size: 1rem;
        }
        .key-box {
            display: inline-block;
            margin: 0.25rem;
            padding: 0.5rem 0.75rem;
            border: 1px solid #555;
            border-radius: 8px;
            background: #222;
        }
        .position {
            margin-top: 1rem;
            font-size: 1rem;
            color: #9ad;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>RC Live Camera Feed</h1>
        <img src="/video_feed" alt="Live camera stream">

        <div class="status">
            Current command: <span id="command">stop</span>
        </div>

        <div class="position">
            Current position: <span id="position">waiting...</span>
        </div>

        <div class="controls">
            Use keyboard controls:
            <div>
                <span class="key-box">W = Forward</span>
                <span class="key-box">A = Left</span>
                <span class="key-box">S = Backward</span>
                <span class="key-box">D = Right</span>
            </div>
            <p>Releasing a movement key sends STOP.</p>
        </div>
    </div>

    <script>
        let activeKeys = new Set();
        let lastDirectionSent = "stop";

        function getDirectionFromKeys() {
            if (activeKeys.has("w")) return "forward";
            if (activeKeys.has("s")) return "backward";
            if (activeKeys.has("a")) return "left";
            if (activeKeys.has("d")) return "right";
            return "stop";
        }

        async function sendDirection(direction) {
            if (direction === lastDirectionSent) {
                return;
            }

            lastDirectionSent = direction;
            document.getElementById("command").textContent = direction;

            try {
                const response = await fetch("/move", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({ command: direction })
                });

                const data = await response.json();
                console.log("Server response:", data);
            } catch (error) {
                console.error("Failed to send direction:", error);
            }
        }

        async function updatePosition() {
            try {
                const response = await fetch("/position");
                const data = await response.json();

                if (data.status === "ok" && data.position) {
                    document.getElementById("position").textContent =
                        `x=${data.position[0].toFixed(2)}, y=${data.position[1].toFixed(2)}`;
                } else {
                    document.getElementById("position").textContent = "waiting...";
                }
            } catch (error) {
                console.error("Failed to fetch position:", error);
            }
        }

        document.addEventListener("keydown", (event) => {
            const key = event.key.toLowerCase();

            if (["w", "a", "s", "d"].includes(key)) {
                event.preventDefault();
                activeKeys.add(key);
                sendDirection(getDirectionFromKeys());
            }
        });

        document.addEventListener("keyup", (event) => {
            const key = event.key.toLowerCase();

            if (["w", "a", "s", "d"].includes(key)) {
                event.preventDefault();
                activeKeys.delete(key);
                sendDirection(getDirectionFromKeys());
            }
        });

        window.addEventListener("blur", () => {
            activeKeys.clear();
            sendDirection("stop");
        });

        setInterval(updatePosition, 500);
        updatePosition();
    </script>
</body>
</html>
"""

def get_position(pos):
    global latest_position
    with position_lock:
        latest_position = pos.tolist() if hasattr(pos, "tolist") else pos
    print("Updated position:", latest_position)

def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            continue

        ret, buffer = cv2.imencode(".jpg", frame)
        if not ret:
            continue

        frame_bytes = buffer.tobytes()
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

@app.route("/move", methods=["POST"])
def move():
    global current_direction

    data = request.get_json(silent=True)
    if not data or "command" not in data:
        return jsonify({"status": "error", "message": "Missing direction"}), 400

    direction = data["command"]
    valid_commands = {"forward", "backward", "left", "right", "stop"}

    if direction not in valid_commands:
        return jsonify({"status": "error", "message": "Invalid command"}), 400

    current_direction = direction
    print(f"Received direction: {direction}")

    return jsonify({"status": "ok", "command": direction})

@app.route("/position")
def position():
    with position_lock:
        if latest_position is None:
            return jsonify({"status": "waiting", "position": None})
        return jsonify({"status": "ok", "position": latest_position})

if __name__ == "__main__":
    start_trilateration(get_position)
    app.run(host="0.0.0.0", port=5001, debug=False)