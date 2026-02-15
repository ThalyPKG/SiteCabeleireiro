from flask import Flask, render_template, request, redirect, session, flash, url_for, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from flask_mail import Mail, Message
from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer
import mysql.connector
import os
import re
import secrets
import hashlib

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
app.config["PROPAGATE_EXCEPTIONS"] = True


app.config["MAIL_SERVER"] = "smtp-relay.brevo.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER")

mail = Mail(app)
ADMIN_EMAIL = os.getenv("MAIL_USERNAME")

serializer = URLSafeTimedSerializer(app.secret_key)



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




def email_valido(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email)


def senha_valida(senha):
    return (
        len(senha) >= 5 and
        any(c.isupper() for c in senha) and
        any(c.islower() for c in senha)
    )



@app.route("/")
def home():
    return redirect(url_for("index"))


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
            flash("Senha fraca", "erro")
            return redirect("/registro")

        db = get_db_login()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM usuario WHERE email=%s", (email,))
        if cursor.fetchone():
            flash("Email já cadastrado", "erro")
            return redirect("/registro")

        senha_hash = generate_password_hash(senha)

        cursor.execute(
            "INSERT INTO usuario (email, senha) VALUES (%s,%s)",
            (email, senha_hash)
        )
        db.commit()

        cursor.close()
        db.close()

        return redirect("/login")

    return render_template("registro.html")



@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]

        db = get_db_login()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM usuario WHERE email=%s", (email,))
        user = cursor.fetchone()

        cursor.close()
        db.close()

        if user and check_password_hash(user["senha"], senha):
            session["usuario_id"] = user["codigo"]
            session["email"] = user["email"]

            flash("Login realizado!", "sucesso")
            return redirect("/index")

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
        return redirect("/login")

    db = get_db_salao()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":

        data = request.form.get("data")
        horario = request.form.get("horario")
        telefone = request.form.get("telefone")
        servicos = request.form.getlist("servicos")
        total = request.form.get("total")

        if not data or not horario or not telefone or not servicos:
            flash("Preencha todos os campos", "erro")
            return redirect("/agendamento")

        cursor.execute("""
            SELECT id FROM agendamentos
            WHERE data=%s AND horario=%s
        """, (data, horario))

        if cursor.fetchone():
            flash("Horário já reservado", "erro")
            return redirect("/agendamento")

        # salva
        cursor.execute("""
            INSERT INTO agendamentos
            (usuario_id,data,horario,servicos,total,telefone,email)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            session["usuario_id"],
            data,
            horario,
            ", ".join(servicos),
            total,
            telefone,
            session["email"]
        ))

        db.commit()
        agendamento_id = cursor.lastrowid

        data_formatada = datetime.strptime(
            data, "%Y-%m-%d"
        ).strftime("%d/%m/%Y")

        mensagem_cliente = f"""
Olá!

Seu agendamento foi confirmado ✅

📅 Data: {data_formatada}
⏰ Horário: {horario}
💇 Serviços: {", ".join(servicos)}
💰 Total: R$ {total}
📞 Telefone: {telefone}
"""

        enviar_email(session["email"], "Agendamento confirmado ✂️", mensagem_cliente)


        mensagem_admin = f"""
NOVO AGENDAMENTO RECEBIDO

Cliente: {session["email"]}
Telefone: {telefone}

Data: {data_formatada}
Horário: {horario}
Serviços: {", ".join(servicos)}
Total: R$ {total}
"""

        enviar_email(ADMIN_EMAIL, "Novo agendamento recebido", mensagem_admin)


        cursor.close()
        db.close()

        return redirect(url_for("confirmacao", id=agendamento_id))


    cursor.execute("SELECT data, horario FROM agendamentos")
    ocupados_db = cursor.fetchall()
    horarios_ocupados = {}

    for ag in ocupados_db:  
        data_obj = ag.get("data")
        horario_obj = ag.get("horario")

        if not data_obj or not horario_obj:
            continue

    # transforma a data em string
        data_str = data_obj.strftime("%Y-%m-%d") if hasattr(data_obj, "strftime") else str(data_obj)

    # transforma horário em string
        if isinstance(horario_obj, timedelta):
            total_minutos = horario_obj.seconds // 60
            h = total_minutos // 60
            m = total_minutos % 60
            hora_str = f"{h:02d}:{m:02d}"
        elif hasattr(horario_obj, "strftime"):
            hora_str = horario_obj.strftime("%H:%M")
        else:
            hora_str = str(horario_obj)[:5]

    # adiciona ao dict
        if data_str not in horarios_ocupados:
            horarios_ocupados[data_str] = []

        horarios_ocupados[data_str].append(hora_str)

# ordena os horários de cada dia
    for dia in horarios_ocupados:
        horarios_ocupados[dia] = sorted(horarios_ocupados[dia], reverse=True)

    cursor.close()
    db.close()

    return render_template("agendamento.html", horarios_ocupados=horarios_ocupados)

  
@app.route("/confirmacao/<int:id>")
def confirmacao(id):

    db = get_db_salao()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM agendamentos WHERE id=%s", (id,))
    agendamento = cursor.fetchone()

    cursor.close()
    db.close()

    if not agendamento:
        flash("Agendamento não encontrado", "erro")
        return redirect("/agendamento")
    if agendamento and agendamento["horario"]:
        agendamento["horario"] = str(agendamento["horario"])[:5]

    return render_template("confirmacao.html",
                           agendamento=agendamento)



@app.route("/agendamentos")
def agendamentos():

    if "usuario_id" not in session:
        return redirect(url_for("login"))

    db = get_db_salao()
    cursor = db.cursor(dictionary=True)

    usuario_id = session["usuario_id"]

    cursor.execute("""
        SELECT id, data, horario, servicos, total, telefone, email
        FROM agendamentos
        WHERE usuario_id = %s
        ORDER BY data DESC, horario DESC
    """, (usuario_id,))

    lista_agendamentos = cursor.fetchall()
    for ag in lista_agendamentos:
        if ag["horario"]:
            ag["horario"] = str(ag["horario"])[:5]

    

    cursor.close()
    db.close()

    return render_template(
        "agendamentos.html",
        agendamentos=lista_agendamentos
    )


@app.route("/contato", methods=["GET", "POST"])
def contato():
    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        mensagem = request.form.get("mensagem")

        msg = Message(
            subject=f"Nova mensagem de contato de {nome}",
            recipients=["thalysondasilvaribeiro@gmail.com"]
        )

        msg.body = f"Nome: {nome}\nEmail: {email}\nMensagem: {mensagem}"
        enviar_email(
            "thalysondasilvaribeiro@gmail.com",
            f"Nova mensagem de contato de {nome}",
            msg.body
        )


        flash("Mensagem enviada com sucesso!", "sucesso")
        return redirect(url_for("index"))

    return render_template("contato.html")

@app.route("/api/horarios/<data>")
def api_horarios(data):

    db = get_db_salao()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT horario FROM agendamentos
        WHERE data=%s
    """, (data,))

    resultados = cursor.fetchall()

    horarios = []

    for r in resultados:
        h = r["horario"]

        if not h:
            continue

        if isinstance(h, timedelta):
            total_minutes = h.seconds // 60
            horas = total_minutes // 60
            minutos = total_minutes % 60
            horarios.append(f"{horas:02d}:{minutos:02d}")

        elif hasattr(h, "strftime"):
            horarios.append(h.strftime("%H:%M"))

        else:
            horarios.append(str(h)[:5])

    cursor.close()
    db.close()

    return jsonify(horarios)



@app.route("/esqueceu-senha", methods=["GET","POST"])
def esqueceu_senha():

    if request.method == "POST":

        email = request.form.get("email")

        db = get_db_login()
        cursor = db.cursor(dictionary=True)

        cursor.execute("SELECT * FROM usuario WHERE email=%s", (email,))
        user = cursor.fetchone()

        cursor.close()
        db.close()

        if not user:
            flash("Email não encontrado", "erro")
            return redirect("/esqueceu-senha")

        token = serializer.dumps(email, salt="reset-senha")

        link = f"{os.getenv('BASE_URL')}{url_for('redefinir_senha', token=token)}"


        msg = Message(
            subject="Redefinição de senha",
            recipients=[email]
        )

        msg.body = f"""
Olá!

Clique no link abaixo para redefinir sua senha:

{link}

Esse link expira em 15 minutos.

Caso não tenho sido você, ignora esse email!
"""



        enviar_email(email, "Redefinição de senha", msg.body)

        flash("Email enviado! Verifique sua caixa.", "sucesso")
        return redirect("/login")

    return render_template("esqueceu-senha.html")


@app.route("/redefinir-senha/<token>", methods=["GET","POST"])
def redefinir_senha(token):

    try:
        email = serializer.loads(
            token,
            salt="reset-senha",
            max_age=900
        )
    except:
        flash("Link inválido ou expirado", "erro")
        return redirect("/login")

    if request.method == "POST":

        nova_senha = request.form.get("senha")

        if not senha_valida(nova_senha):
            flash("Senha fraca", "erro")
            return redirect(request.url)

        senha_hash = generate_password_hash(nova_senha)

        db = get_db_login()
        cursor = db.cursor()

        cursor.execute("""
            UPDATE usuario
            SET senha=%s
            WHERE email=%s
        """, (senha_hash, email))

        db.commit()

        cursor.close()
        db.close()

        flash("Senha redefinida com sucesso!", "sucesso")
        return redirect("/login")

    return render_template("redefinir-senha.html")

@app.route("/sobre")
def sobre():
    return render_template("sobre.html")

from threading import Thread

from sib_api_v3_sdk import Configuration, ApiClient
from sib_api_v3_sdk.api import transactional_emails_api
from sib_api_v3_sdk.models import SendSmtpEmail
import os

def enviar_email(destinatario, assunto, mensagem):
    configuration = Configuration()
    configuration.api_key['api-key'] = os.getenv("BREVO_API_KEY")

    api_client = ApiClient(configuration)
    api_instance = transactional_emails_api.TransactionalEmailsApi(api_client)

    email = SendSmtpEmail(
        to=[{"email": destinatario}],
        subject=assunto,
        html_content=f"<html><body><p>{mensagem}</p></body></html>",
        sender={"name": "Jefferson Cabeleireiro", "email": "thalysondasilvaribeiro@gmail.com"}
    )

    try:
        api_instance.send_transac_email(email)
        print("Email enviado com sucesso!")
    except Exception as e:
        print("Erro ao enviar:", e)






if __name__ == "__main__":
    app.run(debug=True)
