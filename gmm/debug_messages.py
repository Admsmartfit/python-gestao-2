from app import create_app
from app.models.terceirizados_models import HistoricoNotificacao
from sqlalchemy import or_

app = create_app()
with app.app_context():
    h = HistoricoNotificacao.query.order_by(HistoricoNotificacao.id.desc()).all()
    print("Últimas 5 mensagens no banco:")
    for m in h[:5]:
        print(f"ID: {m.id} | Rem: [{m.remetente}] | Dest: [{m.destinatario}] | Dir: [{m.direcao}] | Msg: {m.mensagem[:30]}")
    
    if h:
        m = h[0]
        tel = m.remetente if m.direcao == 'inbound' else m.destinatario
        print(f"\nAnalisando telefone da mensagem: [{tel}]")
        
        from app.models.terceirizados_models import Terceirizado
        from app.models.models import Usuario
        from app.models.estoque_models import Fornecedor
        
        t = Terceirizado.query.first()
        if t: print(f"Exemplo Terceirizado: [{t.nome}] - Telefone: [{repr(t.telefone)}]")
        u = Usuario.query.first()
        if u: print(f"Exemplo Usuario: [{u.nome}] - Telefone: [{repr(u.telefone)}]")
        f = Fornecedor.query.first()
        if f: print(f"Exemplo Fornecedor: [{f.nome}] - Telefone: [{repr(f.telefone)}]")
        
        t_match = Terceirizado.query.filter_by(telefone=tel).first()
        print(f"Match em Terceirizado: {t_match.nome if t_match else 'NÃO'}")

        print(f"\nComparando [{tel}] com cada Terceirizado:")
        for t in Terceirizado.query.all():
            match = (tel == t.telefone)
            print(f"[{tel}] == [{t.telefone}]? {match}")
            if not match:
                # Mostrar onde está a diferença
                if tel.endswith(t.telefone) or t.telefone.endswith(tel):
                    print(f"   -> Prefixo/Sufixo match! ({len(tel)} vs {len(t.telefone)} chars)")
