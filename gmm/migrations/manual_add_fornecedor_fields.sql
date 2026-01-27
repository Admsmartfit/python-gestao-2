-- Adicionar campo forma_contato_alternativa na tabela fornecedores
ALTER TABLE fornecedores ADD COLUMN forma_contato_alternativa TEXT;

-- Criar tabela comunicacoes_fornecedor
CREATE TABLE IF NOT EXISTS comunicacoes_fornecedor (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_compra_id INTEGER NOT NULL,
    fornecedor_id INTEGER NOT NULL,
    tipo_comunicacao VARCHAR(20) NOT NULL,
    direcao VARCHAR(10) NOT NULL,
    mensagem TEXT,
    status VARCHAR(20) DEFAULT 'pendente',
    resposta TEXT,
    data_envio DATETIME DEFAULT CURRENT_TIMESTAMP,
    data_resposta DATETIME,
    FOREIGN KEY (pedido_compra_id) REFERENCES pedidos_compra (id),
    FOREIGN KEY (fornecedor_id) REFERENCES fornecedores (id)
);

-- Criar índices para melhor performance
CREATE INDEX IF NOT EXISTS idx_comunicacoes_pedido ON comunicacoes_fornecedor(pedido_compra_id);
CREATE INDEX IF NOT EXISTS idx_comunicacoes_fornecedor ON comunicacoes_fornecedor(fornecedor_id);
CREATE INDEX IF NOT EXISTS idx_comunicacoes_data ON comunicacoes_fornecedor(data_envio DESC);
