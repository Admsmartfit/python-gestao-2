import unittest
from unittest.mock import MagicMock, patch
from flask import Flask
from app.routes.webhook import validar_webhook
import hmac
import hashlib
import json
import time
from datetime import datetime

class TestWebhook(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config['WEBHOOK_SECRET'] = 'secret-test'
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_validar_webhook_success(self):
        secret = 'secret-test'
        payload = b'{"test":"ok"}'
        signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        
        req = MagicMock()
        req.headers = {'X-Webhook-Signature': f"sha256={signature}"}
        req.get_data.return_value = payload
        req.remote_addr = '191.252.1.1' # Dummy
        # Use simple utc loop
        now_ts = datetime.utcnow().timestamp()
        req.json = {'timestamp': int(now_ts)}
        
        with patch('app.routes.webhook.current_app', self.app):
             self.assertTrue(validar_webhook(req))

    def test_validar_webhook_fail_signature(self):
        req = MagicMock()
        req.headers = {'X-Webhook-Signature': "sha256=invalid"}
        req.get_data.return_value = b'{}'
        
        with patch('app.routes.webhook.current_app', self.app):
             self.assertFalse(validar_webhook(req))

    def test_validar_webhook_old_timestamp(self):
        # 10 minutes ago
        old_time = int(time.time()) - 600
        req = MagicMock()
        # Correct sig, but old time
        secret = 'secret-test' 
        # Payload irrelevant for this test logic branch if sig passes, but let's mock full
        # Actually validation checks sig first. So we need valid sig.
        payload = b'{"timestamp": ' + str(old_time).encode() + b'}'
        signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        
        req.headers = {'X-Webhook-Signature': f"sha256={signature}"}
        req.get_data.return_value = payload
        req.json = {'timestamp': old_time}
        
        with patch('app.routes.webhook.current_app', self.app):
             self.assertFalse(validar_webhook(req))

if __name__ == '__main__':
    unittest.main()
