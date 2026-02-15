from flask import Flask, render_template, request, redirect, session, flash, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from dotenv import load_dotenv
import mysql.connector
import os
import re

load_dotenv()

app = Flask(__name__)

# ================== CONFIGURAÇÃO ==================
app.secret_key = os.getenv("SECRET_KEY") or "chave_teste_fixa"
app.config["PROPAGATE_EXCEPTIONS"] = True

# ================== BANCO DE DADOS ==================
def get_db_login():
    return mysql.connector.connect(
        host=os.getenv("DB_LOGIN_HOST") or "127.0.0.1",
        user=os.getenv("DB_LOGIN_USER") or "root",
        password=os.getenv("DB_LOGIN_PASSWORD") or "",
        database=os.getenv("DB_LOGIN_NAME"),
        port=int(os.getenv("DB_LOGIN_PORT", 3306))
    )

def get_db_salao():
    return mysql.connector.connect(
        host=os.getenv("DB_SALAO_HOST") or "127.0.0.1",
        user=os.getenv("DB_SALAO_USER") or "root",
        password=os.getenv("DB_SALAO_PASSWORD") or "",
        database=os.getenv("DB_SALAO_NAME"),
        port=int(os.getenv("DB_SALAO_PORT", 3306))
    )

# ================== VALIDAÇÃO ==================
def email_valido(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email)

def senha_valida(senha):
    return len(senha) >= 5 and any(c.isupper() for c in senha) and any(c.islower() for c in senha)

# ================== ROTAS ==================
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/index")
def index():
    return render_template("index.html")

@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")

        if not email_valido(email):
            flash("Email inválido", "erro")
            return redirect("/registro")

        if not senha_valida(senha):
            flash("Senha fraca", "erro")
            return redirect("/registro")

        db = get_db_login()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuario WHERE email=%s", (email,))
        if cursor.fetchone():
            flash("Email já cadastrado", "erro")
            cursor.close()
            db.close()
            return redirect("/registro")

        senha_hash = generate_password_hash(senha)
        cursor.execute("INSERT INTO usuario (email, senha) VALUES (%s,%s)", (email, senha_hash))
        db.commit()
        cursor.close()
        db.close()
        flash("Cadastro realizado com sucesso!", "sucesso")
        return redirect("/login")

    return render_template("registro.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")

        db = get_db_login()
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuario WHERE email=%s", (email,))
        user = cursor.fetchone()
        cursor.close()
        db.close()

        if user and check_password_hash(user["senha"], senha):
            session["usuario_id"] = user["codigo"]
            session["email"] = user["email"]
            flash("Login realizado com sucesso!", "sucesso")
            return redirect("/index")
        else:
            flash("Email ou senha inválidos", "erro")
            return redirect("/login")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logout realizado", "sucesso")
    return redirect("/login")

@app.route("/agendamento", methods=["GET", "POST"])
def agendamento():
    if "usuario_id" not in session:
        flash("Faça login primeiro", "erro")
        return redirect("/login")

    db = get_db_salao()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        data = request.form.get("data")
        horario = request.form.get("horario")
        telefone = request.form.get("telefone")
        servicos = request.form.getlist("servicos")
        total = request.form.get("total")

        if not all([data, horario, telefone, servicos, total]):
            flash("Preencha todos os campos", "erro")
            return redirect("/agendamento")

        cursor.execute("SELECT id FROM agendamentos WHERE data=%s AND horario=%s", (data, horario))
        if cursor.fetchone():
            flash("Horário já reservado", "erro")
            return redirect("/agendamento")

        cursor.execute(
            "INSERT INTO agendamentos (usuario_id, data, horario, servicos, total, telefone, email) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (session["usuario_id"], data, horario, ", ".join(servicos), total, telefone, session["email"])
        )
        db.commit()
        agendamento_id = cursor.lastrowid
        cursor.close()
        db.close()
        flash("Agendamento realizado!", "sucesso")
        return redirect(f"/confirmacao/{agendamento_id}")

    # GET: horários ocupados
    cursor.execute("SELECT data, horario FROM agendamentos")
    ocupados = cursor.fetchall()
    cursor.close()
    db.close()

    horarios_ocupados = {}
    for ag in ocupados:
        data_str = ag["data"].strftime("%Y-%m-%d") if hasattr(ag["data"], "strftime") else str(ag["data"])
        hora_str = str(ag["horario"])[:5]
        if data_str not in horarios_ocupados:
            horarios_ocupados[data_str] = []
        horarios_ocupados[data_str].append(hora_str)

    return render_template("agendamento.html", horarios_ocupados=horarios_ocupados)

@app.route("/agendamentos")
def agendamentos():
    if "usuario_id" not in session:
        flash("Faça login primeiro", "erro")
        return redirect("/login")

    db = get_db_salao()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, data, horario, servicos, total, telefone, email "
                   "FROM agendamentos WHERE usuario_id=%s ORDER BY data DESC, horario DESC",
                   (session["usuario_id"],))
    lista = cursor.fetchall()
    cursor.close()
    db.close()

    for ag in lista:
        ag["horario"] = str(ag["horario"])[:5] if ag.get("horario") else "—"

    return render_template("agendamentos.html", agendamentos=lista)

@app.route("/confirmacao/<int:id>")
def confirmacao(id):
    db = get_db_salao()
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM agendamentos WHERE id=%s", (id,))
    ag = cursor.fetchone()
    cursor.close()
    db.close()

    if not ag:
        flash("Agendamento não encontrado", "erro")
        return redirect("/agendamento")

    ag["horario"] = str(ag["horario"])[:5] if ag.get("horario") else "—"
    return render_template("confirmacao.html", agendamento=ag)

# ================== RODAR ==================
if __name__ == "__main__":
    app.run(debug=True)
