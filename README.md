# IoT Motion Dashboard

A simple Flask + SQLite web app for a PIR motion sensor IoT project.
It stores sensor readings, shows a live-updating dashboard, keeps history,
and lets you remotely control one output device (LED, relay, buzzer, etc.).

## Run locally

```
pip install -r requirements.txt
python app.py
```

Visit http://localhost:5000

## ESP8266 PIR control sketch

The repo includes a sketch at `esp8266_pir_control.ino` for an ESP8266/ESP-01 device.
Before uploading it:

1. Set your Wi‑Fi SSID and password in the sketch.
2. Set `SERVER_HOST` to the URL of your Flask app, for example:
   - local testing: `http://192.168.1.50:5000`
   - hosted app: `https://your-app.onrender.com`
3. Use the correct pin configuration for your board:
   - ESP-01: `PIR_PIN = 0`, `LED_PIN = 2` (watch the boot-pin warning)
   - NodeMCU/Wemos D1 Mini: use `D5` / `D6` style pins instead
4. Install the required Arduino libraries in the Arduino IDE:
   - `ESP8266WiFi`
   - `ESP8266HTTPClient`
   - `ArduinoJson`

The sketch checks the PIR sensor every 1.5 seconds, sends `{"motion": 0|1}` to `/api/sensor`, and updates the local output device based on the server's `device_state` response.

## Deploy to Render

1. Push this folder to a GitHub repo.
2. On Render.com: **New +** → **Web Service** → connect your repo.
3. Settings:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
4. Deploy. Render gives you a public URL, e.g. `https://your-app.onrender.com`.

Note: Render's free filesystem is ephemeral (SQLite data resets on redeploy/restart).
That's fine for a class project; for persistence use Render's paid disks or an
external DB (e.g. Postgres).

## Security hardening applied

This project already includes the protections that apply to this simple Flask + SQLite sensor dashboard:

- secret values are read from environment variables instead of being committed to source
- API endpoints validate motion, state, and brightness before writing to SQLite
- prompt JSON parsing is rejected when required fields are missing
- rate limiting is enabled on the write endpoints to reduce brute-force / spam traffic
- security headers are added on every response (`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, HSTS, CSP, and cache control)
- HTTPS redirection is enforced in production when the app is served behind a secure proxy
- no public DB key or file upload path is used in this project, so those checks do not apply here

## API endpoints (for the ESP32 / ESP-01)

| Endpoint          | Method | Purpose                                                    |
|--------------------|--------|-------------------------------------------------------------|
| `/api/sensor`      | POST   | Device sends a reading: `{"motion": 1}` or `{"motion": 0}`  |
| `/api/state`        | GET    | Device polls to check if output should be ON or OFF        |
| `/api/latest`       | GET    | Dashboard polls for latest reading + device state           |
| `/api/history`      | GET    | Dashboard polls for last 25 readings                        |
| `/api/control`      | POST   | Dashboard sends `{"state": "ON"}` or `{"state": "OFF"}`     |

### Example ESP32/ESP-01 Arduino flow
1. Read PIR pin.
2. HTTP POST to `https://your-app.onrender.com/api/sensor` with JSON `{"motion": 1}`.
3. Read `device_state` from the response (or GET `/api/state`) and set the
   output pin (LED/relay) HIGH or LOW accordingly.
4. Repeat every 1–2 seconds.

## Files

- `app.py` — Flask backend (routes + SQLite storage)
- `templates/index.html` — dashboard (auto-refreshes every 2s, no page reload)
- `requirements.txt`, `Procfile` — for Render deployment
