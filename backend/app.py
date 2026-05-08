import os
from flask import Flask
from flask_cors import CORS
from routes.auth import auth_bp
from routes.checkin import checkin_bp
from routes.membership import membership_bp
from routes.admin import admin_bp
from scheduler import start_scheduler
from limiter import limiter

app = Flask(__name__)
CORS(app)
limiter.init_app(app)

app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(checkin_bp, url_prefix='/api')
app.register_blueprint(membership_bp, url_prefix='/api')
app.register_blueprint(admin_bp, url_prefix='/api/admin')

# 启动AI周报定时任务
start_scheduler(app)

@app.route('/health')
def health():
    return {'status': 'ok'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)
