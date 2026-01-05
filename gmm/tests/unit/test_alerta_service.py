import unittest
from unittest.mock import MagicMock, patch
from app.services.alerta_service import AlertaService
from app.services.circuit_breaker import CircuitBreaker

from flask import Flask

class TestAlertaService(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    @patch('app.services.alerta_service.HistoricoNotificacao')
    @patch('app.services.alerta_service.CircuitBreaker')
    @patch('app.services.alerta_service.requests.post')
    @patch('app.services.alerta_service.ConfiguracaoWhatsApp')
    @patch('app.services.alerta_service.db.session')
    def test_verificar_saude_triggers_alert(self, mock_db, mock_config, mock_post, mock_cb, mock_hist):
        # Setup: Rate < 90%
        # Mocking filter chain which uses >= operator on Column
        # We need to ensure the expression 'criado_em >= date' doesn't crash
        mock_hist.criado_em.__ge__.return_value = MagicMock()
        mock_hist.enviado_em.__ge__.return_value = MagicMock()
        
        # total=100, entregues=80 => 80%
        mock_hist.query.filter.return_value.count.side_effect = [100, 80] 
        
        # Setup: CB Closed
        mock_cb.get_state.return_value = 'CLOSED'
        
        # Setup: Queue Fine
        mock_hist.query.filter_by.return_value.count.return_value = 10
        
        # Setup Config Mock
        mock_config_instance = MagicMock()
        mock_config.query.first.return_value = mock_config_instance
        
        with patch('app.services.alerta_service.current_app') as mock_app:
            mock_app.config.get.return_value = 'http://slack-webhook'
            
            AlertaService.verificar_saude()
            
            # Assertions
            # Should have called slack post for low rate
            self.assertTrue(mock_post.called)
            args, _ = mock_post.call_args
            payload = _['json']
            self.assertIn('Taxa de entrega baixa', payload['attachments'][0]['fields'][0]['value'])
            
            # Should update status to 'degradado' (since it is Warning, not Critical)
            self.assertEqual(mock_config_instance.status_saude, 'degradado')

    @patch('app.services.alerta_service.HistoricoNotificacao')
    @patch('app.services.alerta_service.CircuitBreaker')
    @patch('app.services.alerta_service.requests.post')
    @patch('app.services.alerta_service.ConfiguracaoWhatsApp')
    @patch('app.services.alerta_service.db.session')
    def test_verificar_saude_critical_alert(self, mock_db, mock_config, mock_post, mock_cb, mock_hist):
         # Mocking operators
         mock_hist.criado_em.__ge__.return_value = MagicMock()
         mock_hist.enviado_em.__ge__.return_value = MagicMock()

         # Rate ok
         mock_hist.query.filter.return_value.count.side_effect = [100, 95] 
         
         # CB OPEN -> Critical
         mock_cb.get_state.return_value = 'OPEN'
         
         # Queue Fine
         mock_hist.query.filter_by.return_value.count.return_value = 5
         
         mock_config_instance = MagicMock()
         mock_config.query.first.return_value = mock_config_instance

         with patch('app.services.alerta_service.current_app') as mock_app:
            mock_app.config.get.return_value = 'http://slack-webhook'
            
            AlertaService.verificar_saude()
            
            # Should trigger critical alert
            payload = mock_post.call_args[1]['json']
            self.assertEqual(payload['attachments'][0]['color'], '#dc3545') # Critical color
            self.assertEqual(mock_config_instance.status_saude, 'offline')

if __name__ == '__main__':
    unittest.main()
