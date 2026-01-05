import unittest
from unittest.mock import MagicMock, patch
from app.services.whatsapp_service import WhatsAppService

class TestWhatsAppService(unittest.TestCase):
    def test_validar_telefone(self):
        self.assertTrue(WhatsAppService.validar_telefone("5511999999999"))
        self.assertTrue(WhatsAppService.validar_telefone("5511988887777"))
        self.assertFalse(WhatsAppService.validar_telefone("11999999999")) # Sem 55
        self.assertFalse(WhatsAppService.validar_telefone("551199999999")) # Curto
        self.assertFalse(WhatsAppService.validar_telefone("55119999999999")) # Longo

    @patch('app.services.whatsapp_service.WhatsAppService._get_redis')
    def test_circuit_breaker_logic(self, mock_redis_func):
        mock_redis = MagicMock()
        mock_redis_func.return_value = mock_redis
        
        # Test closed circuit
        mock_redis.get.return_value = None
        status, msg = WhatsAppService.check_circuit_breaker()
        self.assertTrue(status)
        
        # Test open circuit (simulated via timestamp in redis)
        import time
        mock_redis.get.return_value = time.time() + 100
        status, msg = WhatsAppService.check_circuit_breaker()
        self.assertFalse(status)
        self.assertIn("OPEN", msg)

if __name__ == '__main__':
    unittest.main()
