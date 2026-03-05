from datetime import datetime
from decimal import Decimal
from sqlalchemy import event
from app.extensions import db
from app.models.models import Usuario, Unidade

class CategoriaEstoque(db.Model):
    __tablename__ = 'categorias_estoque'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(50), unique=True, nullable=False)
    descricao = db.Column(db.Text, nullable=True)

class Estoque(db.Model):
    __tablename__ = 'estoque'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    nome = db.Column(db.String(150), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categorias_estoque.id'))
    unidade_medida = db.Column(db.String(5), nullable=False)
    quantidade_atual = db.Column(db.Numeric(10, 3), nullable=False, default=0)
    quantidade_minima = db.Column(db.Numeric(10, 3), nullable=False, default=5)
    valor_unitario = db.Column(db.Numeric(10, 2), nullable=True)
    localizacao = db.Column(db.String(100), nullable=True)
    unidade_id = db.Column(db.Integer, db.ForeignKey('unidades.id'), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    categoria = db.relationship('CategoriaEstoque', backref='itens')
    unidade = db.relationship('Unidade', backref='estoque_itens')

class Equipamento(db.Model):
    __tablename__ = 'equipamentos'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    unidade_id = db.Column(db.Integer, db.ForeignKey('unidades.id'), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    numero_serie = db.Column(db.String(100), nullable=True)
    qrcode_externo = db.Column(db.Text, nullable=True, unique=True)
    unidade = db.relationship('Unidade', backref='lista_equipamentos')

class OrdemServico(db.Model):
    __tablename__ = 'ordens_servico'
    id = db.Column(db.Integer, primary_key=True)
    numero_os = db.Column(db.String(20), unique=True, nullable=False)
    tecnico_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    unidade_id = db.Column(db.Integer, db.ForeignKey('unidades.id'), nullable=False)
    equipamento_id = db.Column(db.Integer, db.ForeignKey('equipamentos.id'), nullable=True)
    
    tipo_manutencao = db.Column(db.String(20), nullable=False)
    prioridade = db.Column(db.String(20), default='media')
    descricao_problema = db.Column(db.Text, nullable=False)
    descricao_solucao = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='aberta')
    prazo_conclusao = db.Column(db.DateTime, nullable=False)
    
    # Mantemos JSON como legado ou backup, mas usaremos a tabela AnexosOS
    fotos_antes = db.Column(db.JSON, nullable=True)
    fotos_depois = db.Column(db.JSON, nullable=True)
    
    data_abertura = db.Column(db.DateTime, default=datetime.utcnow)
    data_conclusao = db.Column(db.DateTime, nullable=True)
    origem_criacao = db.Column(db.String(20), default='web') # web, whatsapp_bot
    
    # Feedback (RF-014)
    feedback_rating = db.Column(db.Integer, nullable=True) # 1-5
    feedback_comentario = db.Column(db.Text, nullable=True)
    
    tecnico = db.relationship('Usuario', backref='ordens_servico')
    unidade = db.relationship('Unidade', backref='ordens_servico')
    equipamento_rel = db.relationship('Equipamento', backref='ordens')
    movimentacoes = db.relationship('MovimentacaoEstoque', backref='os', lazy=True)
    
    # [cite_start]NOVO RELACIONAMENTO (PRD 3.2.1) [cite: 1093-1103]
    anexos_list = db.relationship('AnexosOS', backref='os', lazy=True, cascade="all, delete-orphan")

    @property
    def custo_total(self):
        total = Decimal('0.00')
        for mov in self.movimentacoes:
            if mov.tipo_movimentacao == 'consumo' and mov.estoque.valor_unitario:
                total += (mov.quantidade * mov.estoque.valor_unitario)
        return total

# [cite_start]NOVA TABELA (PRD 3.2.1) [cite: 1094]
class AnexosOS(db.Model):
    __tablename__ = 'anexos_os'
    id = db.Column(db.Integer, primary_key=True)
    os_id = db.Column(db.Integer, db.ForeignKey('ordens_servico.id'), nullable=False)
    tipo = db.Column(db.String(20), default='foto_antes') # foto_antes, foto_depois
    nome_arquivo = db.Column(db.String(255), nullable=False)
    caminho_arquivo = db.Column(db.String(500), nullable=False)
    tamanho_kb = db.Column(db.Integer)
    upload_em = db.Column(db.DateTime, default=datetime.utcnow)

# ... (imports existentes) ...

class PlanoManutencao(db.Model):
    __tablename__ = 'planos_manutencao'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False) # Ex: "Lubrificação Semanal"
    
    # Pode ser por Categoria (todas as esteiras) ou Equipamento Específico
    categoria_equipamento = db.Column(db.String(50), nullable=True) 
    equipamento_id = db.Column(db.Integer, db.ForeignKey('equipamentos.id'), nullable=True)
    
    frequencia_dias = db.Column(db.Integer, nullable=False) # Ex: 7, 15, 30
    ultima_execucao = db.Column(db.DateTime, nullable=True)
    
    descricao_procedimento = db.Column(db.Text) # Checklist JSON ou Texto
    ativo = db.Column(db.Boolean, default=True)

    equipamento = db.relationship('Equipamento', backref='planos')



class Fornecedor(db.Model):
    __tablename__ = 'fornecedores'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    endereco = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(120), nullable=False)
    telefone = db.Column(db.String(20), nullable=True)
    whatsapp = db.Column(db.String(20), nullable=True)
    cnpj = db.Column(db.String(20), nullable=True)
    forma_contato_alternativa = db.Column(db.Text, nullable=True)  # Site, telefone fixo, etc.
    prazo_medio_entrega_dias = db.Column(db.Float, default=7.0)
    total_pedidos_entregues = db.Column(db.Integer, default=0)
    ativo = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CatalogoFornecedor(db.Model):
    __tablename__ = 'catalogo_fornecedores'
    id = db.Column(db.Integer, primary_key=True)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedores.id'), nullable=False)
    estoque_id = db.Column(db.Integer, db.ForeignKey('estoque.id'), nullable=False)
    preco_atual = db.Column(db.Numeric(10, 2), nullable=True)
    prazo_estimado_dias = db.Column(db.Integer, default=7)

    fornecedor = db.relationship('Fornecedor', backref='catalogo')
    peca = db.relationship('Estoque', backref='fornecedores')

# [NOVO] Histórico de Comunicações com Fornecedores
class ComunicacaoFornecedor(db.Model):
    __tablename__ = 'comunicacoes_fornecedor'
    id = db.Column(db.Integer, primary_key=True)
    pedido_compra_id = db.Column(db.Integer, db.ForeignKey('pedidos_compra.id'), nullable=False)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedores.id'), nullable=False)
    tipo_comunicacao = db.Column(db.String(20), nullable=False)  # whatsapp, email, telefone, site
    direcao = db.Column(db.String(10), nullable=False)  # enviado, recebido
    mensagem = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pendente')  # pendente, enviado, entregue, lido, respondido, erro
    resposta = db.Column(db.Text, nullable=True)
    data_envio = db.Column(db.DateTime, default=datetime.utcnow)
    data_resposta = db.Column(db.DateTime, nullable=True)

    pedido = db.relationship('PedidoCompra', backref='comunicacoes')
    fornecedor = db.relationship('Fornecedor', backref='comunicacoes')

# [NOVO] Saldo por Unidade
class EstoqueSaldo(db.Model):
    __tablename__ = 'estoque_saldo'
    id = db.Column(db.Integer, primary_key=True)
    estoque_id = db.Column(db.Integer, db.ForeignKey('estoque.id'), nullable=False)
    unidade_id = db.Column(db.Integer, db.ForeignKey('unidades.id'), nullable=False)
    quantidade = db.Column(db.Numeric(10, 3), nullable=False, default=0)
    localizacao = db.Column(db.String(100), nullable=True) # Prateleira X, Gaveta Y

    peca = db.relationship('Estoque', backref='saldos')
    unidade = db.relationship('Unidade', backref='estoque_saldos')

    __table_args__ = (
        db.UniqueConstraint('estoque_id', 'unidade_id', name='uq_estoque_unidade'),
    )

# [NOVO] Solicitação de Transferência
class SolicitacaoTransferencia(db.Model):
    __tablename__ = 'solicitacoes_transferencia'
    id = db.Column(db.Integer, primary_key=True)
    estoque_id = db.Column(db.Integer, db.ForeignKey('estoque.id'), nullable=False)
    unidade_origem_id = db.Column(db.Integer, db.ForeignKey('unidades.id'), nullable=False)
    unidade_destino_id = db.Column(db.Integer, db.ForeignKey('unidades.id'), nullable=False)
    solicitante_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    quantidade = db.Column(db.Numeric(10, 3), nullable=False)
    os_id = db.Column(db.Integer, db.ForeignKey('ordens_servico.id'), nullable=True)

    status = db.Column(db.String(20), default='pendente') # pendente, aprovada, rejeitada, concluida
    data_solicitacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_conclusao = db.Column(db.DateTime, nullable=True)
    observacao = db.Column(db.String(255), nullable=True)

    peca = db.relationship('Estoque')
    origem = db.relationship('Unidade', foreign_keys=[unidade_origem_id])
    destino = db.relationship('Unidade', foreign_keys=[unidade_destino_id])
    solicitante = db.relationship('Usuario')
    os_origem = db.relationship('OrdemServico', foreign_keys=[os_id], backref='transferencias_vinculadas')

class PedidoCompra(db.Model):
    __tablename__ = 'pedidos_compra'
    id = db.Column(db.Integer, primary_key=True)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedores.id'), nullable=True)
    estoque_id = db.Column(db.Integer, db.ForeignKey('estoque.id'), nullable=True)  # nullable para itens livres
    quantidade = db.Column(db.Numeric(10, 3), nullable=False)
    data_solicitacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_chegada = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='pendente')

    # Audit fields
    solicitante_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    aprovador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    recebedor_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)

    # One-tap approval token (Phase 3)
    token_aprovacao = db.Column(db.String(64), unique=True, nullable=True)
    token_expira_em = db.Column(db.DateTime, nullable=True)

    # Additional info
    justificativa = db.Column(db.Text, nullable=True)
    unidade_destino_id = db.Column(db.Integer, db.ForeignKey('unidades.id'), nullable=True)

    # Etapa 3 — vínculo com OS
    os_id = db.Column(db.Integer, db.ForeignKey('ordens_servico.id'), nullable=True)

    # Etapa 4 — compras livres (sem item cadastrado no estoque)
    descricao_livre = db.Column(db.String(300), nullable=True)
    categoria_compra = db.Column(db.String(50), nullable=True)  # peca, limpeza, escritorio, ti, outros

    # Vínculo com OrdemCompraLista (lista padrão enviada como uma única ordem)
    ordem_lista_id = db.Column(db.Integer, db.ForeignKey('ordens_compra_lista.id'), nullable=True)

    # v4.0 - Compras Enterprise
    valor_unitario_estimado = db.Column(db.Numeric(12, 2), nullable=True)
    valor_total_estimado = db.Column(db.Numeric(12, 2), nullable=True)
    tier_aprovacao = db.Column(db.Integer, nullable=True)  # 1, 2 ou 3
    data_entrega_prevista = db.Column(db.DateTime, nullable=True)
    data_recebimento = db.Column(db.DateTime, nullable=True)
    rating_fornecedor = db.Column(db.Integer, nullable=True)  # 1-5 estrelas
    tipo_pedido = db.Column(db.String(20), default='catalogo', nullable=False)  # catalogo | cotacao

    fornecedor = db.relationship('Fornecedor', backref='pedidos')
    peca = db.relationship('Estoque')
    solicitante = db.relationship('Usuario', foreign_keys=[solicitante_id])
    aprovador = db.relationship('Usuario', foreign_keys=[aprovador_id])
    recebedor = db.relationship('Usuario', foreign_keys=[recebedor_id])
    unidade_destino = db.relationship('Unidade', foreign_keys=[unidade_destino_id])
    os_origem = db.relationship('OrdemServico', foreign_keys=[os_id], backref='pedidos_vinculados')

    @property
    def valor_display(self):
        v = self.valor_total_estimado or 0
        return f"R$ {float(v):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

    @property
    def tier_label(self):
        return {1: 'Auto (≤ R$500)', 2: 'Gerente (≤ R$5k)', 3: 'Diretoria (> R$5k)'}.get(self.tier_aprovacao, '—')

class ListaCompra(db.Model):
    """Lista de compra padrão / recorrente."""
    __tablename__ = 'listas_compra'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    periodicidade_dias = db.Column(db.Integer, nullable=True)  # 30, 90, 180, etc.
    criador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ativo = db.Column(db.Boolean, default=True)

    criador = db.relationship('Usuario', backref='listas_compra')
    itens = db.relationship('ListaCompraItem', backref='lista', cascade='all, delete-orphan', lazy='joined')


class ListaCompraItem(db.Model):
    """Item de uma lista de compra padrão."""
    __tablename__ = 'lista_compra_itens'
    id = db.Column(db.Integer, primary_key=True)
    lista_id = db.Column(db.Integer, db.ForeignKey('listas_compra.id'), nullable=False)
    estoque_id = db.Column(db.Integer, db.ForeignKey('estoque.id'), nullable=True)
    descricao_livre = db.Column(db.String(300), nullable=True)
    quantidade = db.Column(db.Numeric(10, 3), nullable=False, default=1)
    categoria_compra = db.Column(db.String(50), nullable=True)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey('fornecedores.id'), nullable=True)

    peca = db.relationship('Estoque')
    fornecedor = db.relationship('Fornecedor')


class OrdemCompraLista(db.Model):
    """Ordem de compra gerada a partir de uma lista padrão — agrupa vários pedidos numa única entrada."""
    __tablename__ = 'ordens_compra_lista'
    id = db.Column(db.Integer, primary_key=True)
    lista_id = db.Column(db.Integer, db.ForeignKey('listas_compra.id'), nullable=True)
    nome = db.Column(db.String(200), nullable=False)
    solicitante_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    unidade_destino_id = db.Column(db.Integer, db.ForeignKey('unidades.id'), nullable=True)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    observacao = db.Column(db.Text, nullable=True)

    solicitante = db.relationship('Usuario', foreign_keys=[solicitante_id])
    unidade_destino = db.relationship('Unidade', foreign_keys=[unidade_destino_id])
    lista_origem = db.relationship('ListaCompra')
    pedidos = db.relationship('PedidoCompra', backref='ordem_lista', lazy='joined')

    @property
    def status_geral(self):
        if not self.pedidos:
            return 'vazio'
        statuses = {p.status for p in self.pedidos}
        if all(s in ['concluido', 'cancelado', 'recusado'] for s in statuses):
            return 'concluido' if any(s == 'concluido' for s in statuses) else 'cancelado'
        if any(s in ['aguardando_entrega', 'aprovado', 'cotacao'] for s in statuses):
            return 'em_andamento'
        return 'pendente'

    @property
    def total_itens(self):
        return len(self.pedidos)


class SolicitacaoPeca(db.Model):
    """Solicitação de peça para OS via WhatsApp"""
    __tablename__ = 'solicitacoes_peca'
    id = db.Column(db.Integer, primary_key=True)
    ordem_servico_id = db.Column(db.Integer, db.ForeignKey('ordens_servico.id'), nullable=False)
    estoque_id = db.Column(db.Integer, db.ForeignKey('estoque.id'), nullable=False)
    quantidade = db.Column(db.Numeric(10, 3), nullable=False)
    status = db.Column(db.String(30), default='aguardando_separacao')  # aguardando_separacao, separado, entregue, cancelado
    solicitante_id = db.Column(db.Integer, nullable=True)  # ID do terceirizado

    # Rastreamento
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    separado_em = db.Column(db.DateTime, nullable=True)
    separado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    entregue_em = db.Column(db.DateTime, nullable=True)

    ordem_servico = db.relationship('OrdemServico', backref='solicitacoes_peca')
    estoque = db.relationship('Estoque')
    separado_por = db.relationship('Usuario', foreign_keys=[separado_por_id])


class MovimentacaoEstoque(db.Model):
    __tablename__ = 'movimentacoes_estoque'
    id = db.Column(db.Integer, primary_key=True)
    os_id = db.Column(db.Integer, db.ForeignKey('ordens_servico.id'), nullable=True)
    estoque_id = db.Column(db.Integer, db.ForeignKey('estoque.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    # [NOVO] Rastrear onde ocorreu
    unidade_id = db.Column(db.Integer, db.ForeignKey('unidades.id'), nullable=True)

    tipo_movimentacao = db.Column(db.String(20), nullable=False)
    quantidade = db.Column(db.Numeric(10, 3), nullable=False)
    observacao = db.Column(db.String(255), nullable=True)
    data_movimentacao = db.Column(db.DateTime, default=datetime.utcnow)

    estoque = db.relationship('Estoque', backref='historico')
    usuario = db.relationship('Usuario')
    unidade = db.relationship('Unidade')

# ── v4.0 Compras Enterprise ────────────────────────────────────────────────

class AprovacaoPedido(db.Model):
    """Registro individual de aprovação/rejeição de pedido (permite dual-approval Tier 3)."""
    __tablename__ = 'aprovacoes_pedido'
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos_compra.id'), nullable=False)
    aprovador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    acao = db.Column(db.String(20), nullable=False)  # 'aprovado' | 'rejeitado'
    observacao = db.Column(db.Text, nullable=True)
    via = db.Column(db.String(20), default='web')  # 'web' | 'whatsapp'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    pedido = db.relationship('PedidoCompra', backref='aprovacoes')
    aprovador = db.relationship('Usuario', foreign_keys=[aprovador_id])


class FaturamentoCompra(db.Model):
    """Nota Fiscal e boleto vinculados a um pedido aprovado."""
    __tablename__ = 'faturamentos_compra'
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos_compra.id'), nullable=False, unique=True)
    numero_nf = db.Column(db.String(50), nullable=True)
    valor_faturado = db.Column(db.Numeric(12, 2), nullable=True)
    data_vencimento_boleto = db.Column(db.Date, nullable=True)
    linha_digitavel = db.Column(db.String(100), nullable=True)
    arquivo_nf = db.Column(db.String(300), nullable=True)    # caminho local
    arquivo_boleto = db.Column(db.String(300), nullable=True)
    registrado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    pedido = db.relationship('PedidoCompra', backref=db.backref('faturamento', uselist=False))
    registrado_por = db.relationship('Usuario', foreign_keys=[registrado_por_id])


class OrcamentoUnidade(db.Model):
    """Orçamento mensal por unidade (Budget Tracking)."""
    __tablename__ = 'orcamentos_unidade'
    id = db.Column(db.Integer, primary_key=True)
    unidade_id = db.Column(db.Integer, db.ForeignKey('unidades.id'), nullable=False)
    ano = db.Column(db.Integer, nullable=False)
    mes = db.Column(db.Integer, nullable=False)   # 1-12
    categoria = db.Column(db.String(50), nullable=True)  # peca, limpeza, ti, outros
    valor_orcado = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    unidade = db.relationship('Unidade', backref='orcamentos')
    criado_por = db.relationship('Usuario', foreign_keys=[criado_por_id])


class CotacaoCompra(db.Model):
    """Orçamento individual de fornecedor vinculado a um pedido do tipo 'cotacao'."""
    __tablename__ = 'cotacoes_compra'
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedidos_compra.id'), nullable=False)
    fornecedor_nome = db.Column(db.String(200), nullable=False)
    valor_total = db.Column(db.Numeric(12, 2), nullable=False)
    prazo_dias = db.Column(db.Integer, nullable=True)
    observacao = db.Column(db.Text, nullable=True)
    selecionada = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    pedido = db.relationship('PedidoCompra', backref='cotacoes')

    @property
    def valor_display(self):
        return f"R$ {float(self.valor_total):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')


class ConfiguracaoCompras(db.Model):
    """Configuração global do módulo de compras (singleton)."""
    __tablename__ = 'configuracao_compras'
    id = db.Column(db.Integer, primary_key=True)
    tier1_limite = db.Column(db.Numeric(12, 2), default=500)    # ≤ → auto-aprovado
    tier2_limite = db.Column(db.Numeric(12, 2), default=5000)   # ≤ → gerente; > → diretoria
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)

    updated_by = db.relationship('Usuario', foreign_keys=[updated_by_id])

    @staticmethod
    def get():
        cfg = ConfiguracaoCompras.query.first()
        if not cfg:
            cfg = ConfiguracaoCompras()
            db.session.add(cfg)
            db.session.commit()
        return cfg

# ──────────────────────────────────────────────────────────────────────────────

@event.listens_for(MovimentacaoEstoque, 'after_insert')
def atualizar_saldo_estoque(mapper, connection, target):
    tabela_estoque = Estoque.__table__
    fator = 1
    if target.tipo_movimentacao in ['consumo', 'saida']:
        fator = -1
    qtd_ajuste = target.quantidade * fator
    connection.execute(
        tabela_estoque.update()
        .where(tabela_estoque.c.id == target.estoque_id)
        .values(quantidade_atual=tabela_estoque.c.quantidade_atual + qtd_ajuste)
    )