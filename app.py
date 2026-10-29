from flask import Flask
from settings import SERVICE_NAME, ENVIRONMENT, OWNER

app = Flask(__name__)


@app.route('/')
def index():
    return f"{SERVICE_NAME} [{ENVIRONMENT}] — владелец: {OWNER}"


@app.route('/health')
def health():
    return "ok"


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6080)
