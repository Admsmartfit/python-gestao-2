import unittest
from unittest.mock import MagicMock, patch
from app.services.circuit_breaker import CircuitBreaker
from app.services.rate_limiter import RateLimiter
from app.services.template_service import TemplateService
import json

class TestWhatsAppOutbound(unittest.TestCase):

    def test_template_rendering(self):
        msg = TemplateService.render('novo_chamado', 
            numero_chamado='CH123', 
            titulo='Teste', 
            prazo='31/12', 
            descricao='Desc', 
            link_aceite='http://link'
        )
        self.assertIn('CH123', msg)
        self.assertIn('http://link', msg)

    @patch('app.services.circuit_breaker.CircuitBreaker._get_redis')
    def test_circuit_breaker_logic_full(self, mock_redis_func):
        mock_redis = MagicMock()
        mock_redis_func.return_value = mock_redis
        
        # Simula Estado OPEN
        mock_redis.get.side_effect = lambda k: b'OPEN' if k == 'whatsapp:cb:state' else b'1735600000'
        # Em 1735600000 (aberto), se o tempo agora for +1000s, deve virar HALF_OPEN
        with patch('time.time', return_value=1735600000 + 1000):
            state = CircuitBreaker.get_state()
            self.assertEqual(state, 'HALF_OPEN')

    @patch('app.services.rate_limiter.RateLimiter._get_redis')
    def test_rate_limiter_buckets(self, mock_redis_func):
        mock_redis = MagicMock()
        mock_redis_func.return_value = mock_redis
        
        # Limite atingido
        mock_redis.get.return_value = b'60'
        can_send, rem = RateLimiter.check_limit()
        self.assertFalse(can_send)
        self.assertEqual(rem, 0)

if __name__ == '__main__':
    unittest.main()
