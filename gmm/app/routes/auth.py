from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required
from app.models.models import Usuario
from app.extensions import db

bp = Blueprint('auth', __name__, url_prefix='/auth')

# ... imports ...

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # MUDANÇA: Recebe username em vez de email
        username = request.form.get('username')
        senha = request.form.get('senha')
        
        # Busca por username
        user = Usuario.query.filter_by(username=username).first()

        if user and user.check_senha(senha):
            login_user(user)
            user.ultimo_acesso = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('ponto.index'))
        
        flash('Usuário ou senha incorretos.', 'danger')
    
    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@bp.route('/registrar', methods=['GET', 'POST'])
def registrar():
    if request.method == 'POST':
        nome = request.form.get('nome')
        username = request.form.get('username')
        email = request.form.get('email')
        telefone = request.form.get('telefone')
        senha = request.form.get('senha')
        confirmar_senha = request.form.get('confirmar_senha')

        # Validações
        if not nome or not username or not senha or not confirmar_senha:
            flash('Por favor, preencha todos os campos obrigatórios.', 'danger')
            return render_template('registrar.html')

        if senha != confirmar_senha:
            flash('As senhas não coincidem.', 'danger')
            return render_template('registrar.html')

        if len(senha) < 6:
            flash('A senha deve ter pelo menos 6 caracteres.', 'danger')
            return render_template('registrar.html')

        # Verifica se username já existe
        if Usuario.query.filter_by(username=username).first():
            flash('Este nome de usuário já está em uso.', 'danger')
            return render_template('registrar.html')

        # Verifica se email já existe (se fornecido)
        if email and Usuario.query.filter_by(email=email).first():
            flash('Este e-mail já está cadastrado.', 'danger')
            return render_template('registrar.html')

        # Cria novo usuário
        novo_usuario = Usuario(
            nome=nome,
            username=username,
            email=email if email else None,
            telefone=telefone if telefone else None,
            tipo='comum',  # Tipo padrão para novos registros
            ativo=True
        )
        novo_usuario.set_senha(senha)

        try:
            db.session.add(novo_usuario)
            db.session.commit()
            flash('Cadastro realizado com sucesso! Faça login para continuar.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash('Erro ao criar conta. Tente novamente.', 'danger')
            return render_template('registrar.html')

    return render_template('registrar.html')