import unittest
from unittest.mock import MagicMock, patch
from app.services.roteamento_service import RoteamentoService

class TestWhatsAppRules(unittest.TestCase):
    def setUp(self):
        self.patcher = patch('app.models.terceirizados_models.Terceirizado.query')
        self.mock_terceirizado = self.patcher.start()
        self.mock_terceirizado.filter.return_value.first.return_value = None

        self.patcher2 = patch('app.models.models.Usuario.query')
        self.mock_usuario = self.patcher2.start()
        self.mock_usuario.filter.return_value.first.return_value = None

    def tearDown(self):
        self.patcher.stop()
        self.patcher2.stop()

    @patch('app.models.whatsapp_models.RegrasAutomacao.query')
    def test_unknown_number_rule_match(self, mock_regras_query):
        # Mock a catch-all rule
        mock_rule = MagicMock()
        mock_rule.palavra_chave = '.*'
        mock_rule.tipo_correspondencia = 'regex'
        mock_rule.acao = 'responder'
        mock_rule.resposta_texto = "Test Unknown Response"
        mock_rule.ativo = True
        mock_rule.para_desconhecidos = True
        
        mock_regras_query.filter_by.return_value.order_by.return_value.all.return_value = [mock_rule]

        result = RoteamentoService.processar("5511999999999", "Hello")
        
        self.assertEqual(result['acao'], 'enviar_mensagem')
        self.assertEqual(result['mensagem'], "Test Unknown Response")

    @patch('app.models.whatsapp_models.RegrasAutomacao.query')
    def test_menu_rule_match(self, mock_regras_query):
        # Mock Menu rule
        mock_rule = MagicMock()
        mock_rule.palavra_chave = 'MENU'
        mock_rule.tipo_correspondencia = 'exato'
        mock_rule.acao = 'executar_funcao'
        mock_rule.funcao_sistema = 'exibir_menu_principal'
        mock_rule.ativo = True
        mock_rule.para_desconhecidos = True
        
        mock_regras_query.filter_by.return_value.order_by.return_value.all.return_value = [mock_rule]

        with patch.object(RoteamentoService, '_executar_funcao_sistema') as mock_exec:
            mock_exec.return_value = {'acao': 'responder', 'resposta': 'Menu Content'}
            result = RoteamentoService.processar("5511999999999", "MENU")
            
            mock_exec.assert_called_once()
            self.assertEqual(result['resposta'], 'Menu Content')

if __name__ == '__main__':
    unittest.main()
