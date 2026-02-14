from flask import Flask, render_template, request, redirect, session, flash, url_for, get_flashed_messages
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from flask_mail import Mail, Message
from dotenv import load_dotenv 
import mysql.connector
import re
import secrets
import hashlib
import os

# ---------------- CONFIG ----------------
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# EMAIL
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USE_SSL"] = False
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = ("Jefferson Cabeleireiro", "thalysondasilvaribeiro@gmail.com")
ADMIN_EMAIL = "thalysondasilvaribeiro@gmail.com"

mail = Mail(app)

# ---------------- CONEXÃO BANCO ----------------
db_con = mysql.connector.connect(
    host=os.getenv("MYSQLHOST"),
    user=os.getenv("MYSQLUSER"),
    password=os.getenv("MYSQLPASSWORD"),
    database=os.getenv("MYSQLDATABASE"),
    port=int(os.getenv("MYSQLPORT"))
)

# ---------------- CRIAR TABELAS ----------------
def criar_tabelas():
    cursor = db_con.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuario (
        codigo INT AUTO_INCREMENT PRIMARY KEY,
        email VARCHAR(255) NOT NULL UNIQUE,
        senha VARCHAR(255) NOT NULL
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS password_resets (
        id INT AUTO_INCREMENT PRIMARY KEY,
        email VARCHAR(255) NOT NULL,
        token VARCHAR(255) NOT NULL,
        expires_at DATETIME NOT NULL
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agendamentos (
        id INT AUTO_INCREMENT PRIMARY KEY,
        usuario_id INT,
        data DATE NOT NULL,
        horario TIME NOT NULL,
        servicos TEXT NOT NULL,
        total DECIMAL(10,2) NOT NULL,
        telefone VARCHAR(20) NOT NULL,
        email VARCHAR(255) NOT NULL
    )""")
    db_con.commit()

criar_tabelas()

# ---------------- FUNÇÕES ----------------
def email_valido(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email)

def senha_valida(senha):
    return len(senha) >= 5 and any(c.isupper() for c in senha) and any(c.islower() for c in senha)

def gerar_token_reset():
    return secrets.token_urlsafe(32)

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def enviar_email_reset(email, link):
    msg = Message(
        subject="Redefinição de senha",
        recipients=[email]
    )
    msg.body = f"""Olá!\n\nRecebemos uma solicitação para redefinir sua senha.\n\nAbra o link abaixo:\n{link}\n\nLink expira em 30 minutos.\nSe você não solicitou, ignore."""
    msg.html = f"""
    <p>Olá!</p>
    <p>Recebemos uma solicitação para redefinir sua senha.</p>
    <p><a href="{link}">Redefinir Senha</a></p>
    <p><b>Expira em 30 minutos</b></p>
    <p>Se você não solicitou, ignore.</p>
    """
    mail.send(msg)

# ---------------- ROTAS ----------------
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
            flash("Senha inválida (min 5 chars, 1 maiúscula, 1 minúscula)", "erro")
            return redirect("/registro")

        cursor = db_con.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuario WHERE email=%s", (email,))
        if cursor.fetchone():
            flash("Email já cadastrado!", "erro")
            return redirect("/registro")

        senha_hash = generate_password_hash(senha)
        cursor.execute("INSERT INTO usuario (email, senha) VALUES (%s,%s)", (email, senha_hash))
        db_con.commit()
        flash("Cadastro realizado com sucesso!", "sucesso")
        return redirect("/login")
    return render_template("registro.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]
        lembrar = request.form.get("lembrar")

        cursor = db_con.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuario WHERE email=%s", (email,))
        user = cursor.fetchone()

        if user and check_password_hash(user["senha"], senha):
            session["usuario_id"] = user["codigo"]
            session["email"] = user["email"]
            session.permanent = bool(lembrar)
            if lembrar:
                app.permanent_session_lifetime = timedelta(days=30)
            flash("Login realizado com sucesso!", "sucesso")
            return redirect("/index")
        else:
            flash("Email ou senha inválidos", "erro")
            return redirect("/login")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logout realizado com sucesso!", "sucesso")
    return redirect("/login")

@app.route("/esqueceu-senha", methods=["GET","POST"])
def esqueceu_senha():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        flash("Se o e-mail existir, você receberá um link para redefinir a senha.", "sucesso")

        cursor = db_con.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuario WHERE email=%s", (email,))
        user = cursor.fetchone()
        if user:
            token_puro = gerar_token_reset()
            token_hash = hash_token(token_puro)
            cursor.execute("DELETE FROM password_resets WHERE email=%s", (email,))
            db_con.commit()
            expires_at = datetime.utcnow() + timedelta(minutes=30)
            cursor.execute("INSERT INTO password_resets (email, token, expires_at) VALUES (%s,%s,%s)",
                           (email, token_hash, expires_at))
            db_con.commit()
            link = url_for("redefinir_senha", token=token_puro, _external=True)
            enviar_email_reset(email, link)
        return redirect("/esqueceu-senha")
    return render_template("esqueceu-senha.html")

@app.route("/redefinir-senha/<token>", methods=["GET","POST"])
def redefinir_senha(token):
    token_hash = hash_token(token)
    cursor = db_con.cursor(dictionary=True)
    cursor.execute("SELECT * FROM password_resets WHERE token=%s", (token_hash,))
    reset = cursor.fetchone()

    if not reset or reset["expires_at"] < datetime.utcnow():
        if reset:
            cursor.execute("DELETE FROM password_resets WHERE id=%s", (reset["id"],))
            db_con.commit()
        flash("Link inválido ou expirado.", "erro")
        return redirect("/esqueceu-senha")

    if request.method == "POST":
        senha = request.form["senha"]
        confirmar = request.form["confirmar"]
        if senha != confirmar:
            flash("As senhas não conferem.", "erro")
            return redirect(url_for("redefinir_senha", token=token))
        if not senha_valida(senha):
            flash("Senha inválida.", "erro")
            return redirect(url_for("redefinir_senha", token=token))

        senha_hash = generate_password_hash(senha)
        cursor.execute("UPDATE usuario SET senha=%s WHERE email=%s", (senha_hash, reset["email"]))
        cursor.execute("DELETE FROM password_resets WHERE id=%s", (reset["id"],))
        db_con.commit()
        flash("Senha redefinida com sucesso!", "sucesso")
        return redirect("/login")

    return render_template("redefinir-senha.html")

@app.route("/agendamento", methods=["GET","POST"])
def agendamento():
    if "usuario_id" not in session:
        return redirect("/login")
    cursor = db_con.cursor(dictionary=True)

    if request.method == "POST":
        usuario_id = session["usuario_id"]
        data = request.form.get("data")
        horario = request.form.get("horario")
        servicos = request.form.getlist("servicos")
        total = request.form.get("total")
        telefone = request.form.get("telefone")
        email = session["email"]

        # Validações
        if not data or not horario or not servicos or not telefone:
            flash("Preencha todos os campos obrigatórios.", "erro")
            return redirect("/agendamento")

        cursor.execute("SELECT * FROM agendamentos WHERE data=%s AND horario=%s", (data, horario))
        if cursor.fetchone():
            flash("Horário já reservado.", "erro")
            return redirect("/agendamento")

        servicos_str = ", ".join(servicos)
        cursor.execute("""INSERT INTO agendamentos
                          (usuario_id, data, horario, servicos, total, telefone, email)
                          VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                       (usuario_id, data, horario, servicos_str, total, telefone, email))
        db_con.commit()
        agendamento_id = cursor.lastrowid

        # Email usuário
        data_formatada = datetime.strptime(data, "%Y-%m-%d").strftime("%d/%m/%Y")
        msg = Message(subject="Agendamento Confirmado - Jefferson Cabeleireiro", recipients=[email])
        msg.body = f"Olá!\n\nSeu agendamento foi confirmado 🎉\nData: {data_formatada}\nHorário: {horario}\nServiços: {servicos_str}\nTotal: R$ {total}\nPagamento presencial."
        mail.send(msg)

        # Email admin
        msg_admin = Message(subject="📅 Novo Agendamento Recebido", recipients=[ADMIN_EMAIL])
        msg_admin.body = f"Cliente: {email}\nTelefone: {telefone}\nData: {data_formatada}\nHorário: {horario}\nServiços: {servicos_str}\nTotal: R$ {total}"
        mail.send(msg_admin)

        return redirect(url_for("confirmacao", id=agendamento_id))

    # GET
    cursor.execute("SELECT data, horario FROM agendamentos")
    ocupados = cursor.fetchall()
    horarios_ocupados = {}
    for item in ocupados:
        dia = item['data'].strftime("%Y-%m-%d")
        horario_str = item['horario'].strftime("%H:%M") if isinstance(item['horario'], datetime.time) else str(item['horario'])
        horarios_ocupados.setdefault(dia, []).append(horario_str)

    return render_template("agendamento.html", horarios_ocupados=horarios_ocupados)

@app.route("/confirmacao/<int:id>")
def confirmacao(id):
    cursor = db_con.cursor(dictionary=True)
    cursor.execute("SELECT * FROM agendamentos WHERE id=%s", (id,))
    agendamento = cursor.fetchone()
    if not agendamento:
        flash("Agendamento não encontrado.", "erro")
        return redirect("/agendamento")
    return render_template("confirmacao.html", agendamento=agendamento)

@app.route("/agendamentos")
def agendamentos():
    if "usuario_id" not in session:
        return redirect("/login")
    usuario_id = session["usuario_id"]
    cursor = db_con.cursor(dictionary=True)
    cursor.execute("""SELECT id, data, horario, servicos, total, telefone, email
                      FROM agendamentos WHERE usuario_id=%s ORDER BY data DESC, horario DESC""", (usuario_id,))
    agendamentos = cursor.fetchall()
    return render_template("agendamentos.html", agendamentos=agendamentos)

@app.route("/contato", methods=["GET","POST"])
def contato():
    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        mensagem = request.form.get("mensagem")
        msg = Message(subject=f"Nova mensagem de contato de {nome}", recipients=[ADMIN_EMAIL])
        msg.body = f"Nome: {nome}\nEmail: {email}\nMensagem: {mensagem}"
        mail.send(msg)
        flash("Mensagem enviada com sucesso!", "sucesso")
        return redirect("/index")
    return render_template("contato.html")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
