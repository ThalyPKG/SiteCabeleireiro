from flask import Flask, render_template, request, redirect, session, flash, url_for, get_flashed_messages, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from flask_mail import Mail, Message
from dotenv import load_dotenv 
load_dotenv()
import mysql.connector
import re
import secrets
import hashlib
import os


app = Flask(__name__)

# CONFIG EMAIL (Gmail)

app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USE_SSL"] = False

app.secret_key = os.getenv("SECRET_KEY")

app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")

app.config["MAIL_DEFAULT_SENDER"] = ("Jefferson Cabeleireiro", "thalysondasilvaribeiro@gmail.com")
ADMIN_EMAIL = "thalysondasilvaribeiro@gmail.com"


mail = Mail(app)

# CONEXÃO BANCO LOGIN
db_login = mysql.connector.connect(
    host=os.getenv("MYSQLHOST"),
    user=os.getenv("MYSQLUSER"),
    password=os.getenv("MYSQLPASSWORD"),
    database=os.getenv("MYSQLDATABASE"),
    port=int(os.getenv("MYSQLPORT"))
)

db_salao = mysql.connector.connect(
    host=os.getenv("MYSQLHOST"),
    user=os.getenv("MYSQLUSER"),
    password=os.getenv("MYSQLPASSWORD"),
    database=os.getenv("MYSQLDATABASE"),
    port=int(os.getenv("MYSQLPORT"))
)


def criar_tabelas():
    cursor_login = db_login.cursor()
    cursor_salao = db_salao.cursor()

    # Tabela usuario
    cursor_login.execute("""
    CREATE TABLE IF NOT EXISTS usuario (
        codigo INT AUTO_INCREMENT PRIMARY KEY,
        email VARCHAR(255) NOT NULL UNIQUE,
        senha VARCHAR(255) NOT NULL
    )
    """)

    # Tabela password_resets
    cursor_login.execute("""
    CREATE TABLE IF NOT EXISTS password_resets (
        id INT AUTO_INCREMENT PRIMARY KEY,
        email VARCHAR(255) NOT NULL,
        token VARCHAR(255) NOT NULL,
        expires_at DATETIME NOT NULL
    )
    """)

    # Tabela agendamentos
    cursor_salao.execute("""
    CREATE TABLE IF NOT EXISTS agendamentos (
        id INT AUTO_INCREMENT PRIMARY KEY,
        usuario_id INT,
        data DATE NOT NULL,
        horario TIME NOT NULL,
        servicos TEXT NOT NULL,
        total DECIMAL(10,2) NOT NULL,
        telefone VARCHAR(20) NOT NULL,
        email VARCHAR(255) NOT NULL
    )
    """)

    db_login.commit()
    db_salao.commit()

criar_tabelas()



# Funções de validação
def email_valido(email):
    padrao = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(padrao, email)

def senha_valida(senha):
    if len(senha) < 5:
        return False
    if not any(c.isupper() for c in senha):
        return False
    if not any(c.islower() for c in senha):
        return False
    return True

# ROTAS

@app.route("/")
def home():
    return redirect("/index")

@app.route("/index")
def index():
    return render_template("index.html")

@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]

        if not email_valido(email):
            flash("Email inválido", "erro")
            return redirect("/registro")

        if not senha_valida(senha):
            flash("A senha deve ter no mínimo 5 caracteres e 1 letra maiuscúla", "erro")
            return redirect("/registro")
        
        senha_hash = generate_password_hash(senha)

        cursor = db_login.cursor()

        cursor.execute("SELECT * FROM usuario WHERE email = %s", (email,))
        usuario = cursor.fetchone()

        if usuario:
            flash("Esse email já está cadastrado!", "erro")
            return redirect("/registro")

        cursor.execute(
            "INSERT INTO usuario (email, senha) VALUES (%s, %s)",
            (email, senha_hash)
        )
        db_login.commit()

        return redirect("/login")

    return render_template("registro.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]
        lembrar = request.form.get("lembrar")

        cursor = db_login.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuario WHERE email=%s",(email,))
        user = cursor.fetchone()

        if user and check_password_hash(user["senha"], senha):
            session["usuario_id"] = user["codigo"]
            session["email"] = user["email"]

            if lembrar:
                # mantém sessão por 30 dias
                session.permanent = True
                app.permanent_session_lifetime = timedelta(days=30)
            else:
                session.permanent = False

            flash("Login realizado com sucesso!", "sucesso") 
            return redirect("/index")
        else:
            flash("Email ou senha inválidos", "erro")
            return redirect("/login")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()  # remove todas as informações da sessão
    flash("Você saiu da conta com sucesso!", "sucesso")
    return redirect(url_for("login"))

@app.route("/esqueceu-senha", methods=["GET", "POST"])
def esqueceu_senha():
    if request.method == "POST":
        email = request.form["email"].strip().lower()

        # mensagem SEMPRE igual (segurança)
        flash("Se o e-mail existir, você receberá um link para redefinir a senha.", "sucesso")

        cursor = db_login.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuario WHERE email=%s", (email,))
        user = cursor.fetchone()

        if user:
            token_puro = gerar_token_reset()
            token_hash = hash_token(token_puro)

            # apaga resets antigos desse email
            cursor.execute("DELETE FROM password_resets WHERE email=%s", (email,))
            db_login.commit()

            # cria reset novo
            expires_at = datetime.utcnow() + timedelta(minutes=30)
            cursor.execute(
                "INSERT INTO password_resets (email, token, expires_at) VALUES (%s, %s, %s)",
                (email, token_hash, expires_at)
            )
            db_login.commit()

            link = url_for("redefinir_senha", token=token_puro, _external=True)

            # aqui você chama sua função real de email
            enviar_email_reset(email, link)

        return redirect(url_for("esqueceu_senha"))

    return render_template("esqueceu-senha.html")

@app.route("/redefinir-senha/<token>", methods=["GET", "POST"])
def redefinir_senha(token):

    get_flashed_messages()
    token_hash = hash_token(token)

    cursor = db_login.cursor(dictionary=True)
    cursor.execute("SELECT * FROM password_resets WHERE token=%s", (token_hash,))
    reset = cursor.fetchone()

    if not reset:
        flash("Link inválido ou expirado. Solicite novamente.", "erro")
        return redirect(url_for("esqueceu_senha"))

    if reset["expires_at"] < datetime.utcnow():
        # remove token expirado
        cursor.execute("DELETE FROM password_resets WHERE id=%s", (reset["id"],))
        db_login.commit()

        flash("Link inválido ou expirado. Solicite novamente.", "erro")
        return redirect(url_for("esqueceu_senha"))

    if request.method == "POST":
        senha = request.form["senha"]
        confirmar = request.form["confirmar"]

        if senha != confirmar:
            flash("As senhas não conferem.", "erro")
            return redirect(url_for("redefinir_senha", token=token))

        if not senha_valida(senha):
            flash("Email ou senha inválidos.", "erro")
            return redirect(url_for("redefinir_senha", token=token))


        # troca senha do usuário
        senha_hash = generate_password_hash(senha)

        cursor.execute("UPDATE usuario SET senha=%s WHERE email=%s", (senha_hash, reset["email"]))
        db_login.commit()

        # invalida token (deleta do banco)
        cursor.execute("DELETE FROM password_resets WHERE id=%s", (reset["id"],))
        db_login.commit()

        flash("Senha redefinida com sucesso! Agora faça login.", "sucesso")
        return redirect(url_for("login"))

    return render_template("redefinir-senha.html")

def gerar_token_reset():
    return secrets.token_urlsafe(32)

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def enviar_email_reset(email, link):
    msg = Message (
        subject="Redefinição de senha",
        recipients=[email]
    )

    msg.body = f"""Olá!

Recebemos uma solicitação para redefinir sua senha.

Abra o link abaixo para criar uma nova senha:
{link}

Esse link expira em 30 minutos.

Se você não solicitou isso, ignore este email.
"""

    msg.html = f"""
    <p>Olá!</p>
    <p>Recebemos uma solicitação para redefinir sua senha.</p>
    <p>Abra o link abaixo para criar uma nova senha:</p>
    <p><a href="{link}">Redefinir Senha</a></p>
    <p><b>Esse link expira em 30 minutos.</b></p>
    <p>Se você não solicitou isso, ignore este email.</p>
    """
    mail.send(msg)

@app.route("/agendamento", methods=["GET", "POST"])
def agendamento():
    if "usuario_id" not in session:
        return redirect("/login")

    cursor = db_salao.cursor(dictionary=True)

    # ------------------- POST -------------------
    if request.method == "POST":
        usuario_id = session.get("usuario_id")
        data = request.form.get("data")
        horario = request.form.get("horario")
        servicos = request.form.getlist("servicos")
        total = request.form.get("total")
        telefone = request.form.get("telefone")
        email = session.get("email")

        # VALIDAÇÕES
        if not data:
            flash("Selecione uma data.", "erro")
            return redirect("/agendamento")

        if not horario:
            flash("Selecione um horário.", "erro")
            return redirect("/agendamento")

        if not servicos:
            flash("Selecione pelo menos um serviço.", "erro")
            return redirect("/agendamento")

        if not telefone:
            flash("Informe o telefone.", "erro")
            return redirect("/agendamento")

        servicos_str = ", ".join(servicos)

        # VERIFICAR SE HORÁRIO JÁ EXISTE
        cursor.execute("""
            SELECT * FROM agendamentos
            WHERE data = %s AND horario = %s
        """, (data, horario))
        existente = cursor.fetchone()
        if existente:
            flash("Esse horário já foi reservado.", "erro")
            return redirect("/agendamento")

        # SALVAR NO BANCO
        cursor.execute("""
            INSERT INTO agendamentos
            (usuario_id, data, horario, servicos, total, telefone, email)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (usuario_id, data, horario, servicos_str, total, telefone, email))
        db_salao.commit()

        agendamento_id = cursor.lastrowid

        # ENVIAR EMAIL
       
        data_formatada = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")

        msg = Message(
            subject="Agendamento Confirmado - Jefferson Cabeleireiro",
            recipients=[email]
        )
        msg.body = f"""

Olá!

Seu agendamento foi confirmado 🎉

Data: {data_formatada}
Horário: {horario}
Serviços: {', '.join(servicos)}
Total: R$ {total}

O pagamento será realizado presencialmente no dia do atendimento.

Obrigado por escolher Jefferson Cabeleireiro!
"""
        mail.send(msg)

# aviso email admin
        msg_admin = Message(
            subject="📅 Novo Agendamento Recebido",
            recipients=[ADMIN_EMAIL]
        )

        msg_admin.body = f"""
Novo agendamento realizado!

Cliente: {email}
Telefone: {telefone}

Data: {data_formatada}
Horário: {horario}
Serviços: {servicos_str}
Total: R$ {total}
"""

        mail.send(msg_admin)


        return redirect(url_for("confirmacao", id=agendamento_id))

        

    # ------------------- GET -------------------
    cursor.execute("SELECT data, horario FROM agendamentos")
    ocupados = cursor.fetchall()

    horarios_ocupados = {}
    for item in ocupados:
        dia = item['data'].strftime("%Y-%m-%d")
        if isinstance(item['horario'], timedelta):
            total_seconds = item['horario'].total_seconds()
            horas = int(total_seconds // 3600)
            minutos = int((total_seconds % 3600) // 60)
            horario_str = f"{horas:02d}:{minutos:02d}"
        else:
            horario_str = str(item['horario'])

        if dia not in horarios_ocupados:
            horarios_ocupados[dia] = []

        horarios_ocupados[dia].append(horario_str)

    return render_template("agendamento.html", horarios_ocupados=horarios_ocupados)

@app.route("/confirmacao/<int:id>")
def confirmacao(id):

    cursor = db_salao.cursor(dictionary=True)
    cursor.execute("SELECT * FROM agendamentos WHERE id = %s", (id,))
    agendamento = cursor.fetchone()

    if not agendamento:
        flash("Agendamento não encontrado.", "erro")
        return redirect("/agendamento")

    return render_template("confirmacao.html", agendamento=agendamento)

    total = request.form.get("total")

    preference_data = {
        "items": [
            {
                "title": "Agendamento - Jefferson Cabeleireiro",
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": float(total)
            }
        ],
        "back_urls": {
            "success": "http://127.0.0.1:5000/sucesso",
            "failure": "http://127.0.0.1:5000/falha",
            "pending": "http://127.0.0.1:5000/pendente"
        },
        "auto_return": "approved"
    }

    preference_response = sdk.preference().create(preference_data)
    preference = preference_response["response"]

    return redirect(preference["init_point"])

@app.route("/sucesso")
def sucesso():
    return "Pagamento aprovado ✅"

@app.route("/falha")
def falha():
    return "Pagamento não concluído ❌"

@app.route("/pendente")
def pendente():
    return "Pagamento pendente ⏳"

@app.route("/contato", methods=["GET", "POST"])
def contato():
    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        mensagem = request.form.get("mensagem")

        # monta email
        msg = Message(
            subject=f"Nova mensagem de contato de {nome}",
            recipients=["thalysondasilvaribeiro@gmail.com"]
        )
        msg.body = f"Nome: {nome}\nEmail: {email}\nMensagem: {mensagem}"
        mail.send(msg)

        flash("Mensagem enviada com sucesso!", "sucesso")
        return redirect(url_for("index"))

    return render_template("contato.html")

@app.route("/agendamentos")
def agendamentos():
    if "usuario_id" not in session:
        return redirect("/login")

    usuario_id = session["usuario_id"]

    cursor = db_salao.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, data, horario, servicos, total, telefone, email
        FROM agendamentos
        WHERE usuario_id = %s
        ORDER BY data DESC, horario DESC
    """, (usuario_id,))

    agendamentos = cursor.fetchall()

    agendamentos.sort(key=lambda x: (x['data'], x['horario']), reverse=True)

    return render_template("agendamentos.html", agendamentos=agendamentos)





if __name__ == "__main__":
    app.run(debug=True)
