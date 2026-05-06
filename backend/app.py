import os
from flask import Flask
from flask_cors import CORS
from routes.auth import auth_bp
from routes.checkin import checkin_bp

app = Flask(__name__)
CORS(app)

app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(checkin_bp, url_prefix='/api')

@app.route('/health')
def health():
    return {'status': 'ok'}

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)
