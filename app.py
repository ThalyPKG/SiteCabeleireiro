from flask import Flask, render_template, request, redirect, session, flash, url_for, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer
import mysql.connector
import os
import re

def limpar_horarios_passados():
    db = get_db_salao()
    cursor = db.cursor()

    agora = datetime.utcnow() - timedelta(hours=3)

    cursor.execute("""
        DELETE FROM agendamentos
        WHERE CONCAT(data, ' ', horario) < %s
    """, (agora,))

    db.commit()
    cursor.close()
    db.close()


load_dotenv()

app = Flask(__name__)

# ================== CONFIGURAÇÃO ==================
app.secret_key = os.getenv("SECRET_KEY") or "chave_teste_fixa"
app.config["PROPAGATE_EXCEPTIONS"] = True
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"


serializer = URLSafeTimedSerializer(app.secret_key)

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
            flash("Login realizado com sucesso!", "login")
            return redirect("/index")
        else:
            flash("Email ou senha inválidos", "login")
            return redirect("/login")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logout realizado", "sucesso")
    return redirect("/login")

@app.route("/agendamento", methods=["GET", "POST"])
def agendamento():
    limpar_horarios_passados()

    hoje = datetime.now().strftime("%Y-%m-%d")
    if "usuario_id" not in session:
        flash("Faça login primeiro", "erro")
        return redirect("/login")

    db = get_db_salao()
    cursor = db.cursor(dictionary=True)

    if request.method == "POST":
        data = request.form.get("data")
        horario = request.form.get("horario")

        try:
            data_hora_agendamento = datetime.strptime(
                f"{data} {horario}",
                "%Y-%m-%d %H:%M"
            )
        except:
            flash("Data ou horário inválido", "erro")
            return redirect("/agendamento")

        agora = datetime.utcnow() - timedelta(hours=3)

        if data_hora_agendamento <= agora:
            flash("Não é possível agendar em horários que já passaram.", "erro")
            return redirect("/agendamento")

        telefone = request.form.get("telefone")
        servicos = request.form.getlist("servicos")
        total = request.form.get("total")

        if not all([data, horario, telefone, servicos, total]):
            flash("Preencha todos os campos", "erro")
            return redirect("/agendamento")

        cursor.execute("""
            SELECT data, horario
            FROM agendamentos
            WHERE usuario_id = %s
            AND data <= %s
            ORDER BY data DESC, horario DESC
            LIMIT 1
        """, (session["usuario_id"], data))

        ultimo_agendamento = cursor.fetchone()

        if ultimo_agendamento:
            data_existente = ultimo_agendamento["data"]
            horario_existente = ultimo_agendamento["horario"]

            if hasattr(data_existente, "strftime"):
                data_existente = data_existente.strftime("%Y-%m-%d")

            if hasattr(horario_existente, "strftime"):
                horario_existente = horario_existente.strftime("%H:%M:%S")
            else:
                horario_existente = str(horario_existente)

            horario_existente = horario_existente.split(":")
            horario_existente = f"{horario_existente[0]}:{horario_existente[1]}"
            

            agendamento_existente = datetime.strptime(
                f"{data_existente} {horario_existente}",
                "%Y-%m-%d %H:%M"
            )

            proximo_permitido = agendamento_existente + timedelta(days=15)

            if data_hora_agendamento < proximo_permitido:
                dias_restantes = (proximo_permitido - data_hora_agendamento).days

                cursor.close()
                db.close()

                flash(
                    f"Você só pode agendar novamente a partir de {proximo_permitido.strftime('%d/%m/%Y')}.",
                    "erro"
                )
                return redirect("/agendamento")


        cursor.execute("SELECT id FROM agendamentos WHERE data=%s AND horario=%s", (data, horario))
        if cursor.fetchone():
            cursor.close()
            db.close()
            flash("Horário já reservado", "erro")
            return redirect("/agendamento")

        cursor.execute(
            "INSERT INTO agendamentos (usuario_id, data, horario, servicos, total, telefone, email) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (session["usuario_id"], data, horario, ", ".join(servicos), total, telefone, session["email"])
        )
        
        db.commit()

# ================= EMAILS =================

        servicos_txt = ", ".join(servicos)

        mensagem_admin = f"""
Novo agendamento realizado!

Cliente: {session["email"]}
Telefone: {telefone}

Data: {data}
Horário: {horario}

Serviços: {servicos_txt}
Total: R$ {total}
"""

        mensagem_cliente = f"""
Seu agendamento foi confirmado ✅

Data: {data}
Horário: {horario}

Serviços: {servicos_txt}
Total: R$ {total}

Caso precise alterar, entre em contato.
"""

# email do dono
        enviar_email(
            "thalysondasilvaribeiro@gmail.com",
            "Novo agendamento recebido",
            mensagem_admin
        )

# email do cliente
        enviar_email(
            session["email"],
            "Confirmação de agendamento",
            mensagem_cliente
        )

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

    return render_template("agendamento.html", horarios_ocupados=horarios_ocupados, hoje=hoje)

@app.route("/agendamentos")
def agendamentos():
    limpar_horarios_passados()
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

@app.route("/contato", methods=["GET", "POST"])
def contato():
    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        mensagem = request.form.get("mensagem")

        mensagem_email = f"""
        Nome: {nome}
        Email: {email}

        Mensagem:
        {mensagem}
        """

        enviar_email(
            "thalysondasilvaribeiro@gmail.com",
            f"Nova mensagem de contato de {nome}",
            mensagem_email
        )

        return redirect(url_for("mensagem_enviada"))

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

        base_url = os.getenv("BASE_URL") or request.host_url
        link = f"{base_url.rstrip('/')}{url_for('redefinir_senha', token=token)}"

        mensagem_email = f"""
        Olá!

        Clique no link abaixo para redefinir sua senha:

        {link}

        Esse link expira em 15 minutos.

        Caso não tenha sido você, ignore este email.
        """

        enviar_email(email, "Redefinição de senha", mensagem_email)

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

def enviar_email(destinatario, assunto, mensagem):

    def enviar():
        try:
            api_key = os.getenv("BREVO_API_KEY")
            if not api_key:
                print("BREVO_API_KEY não configurada")
                return

            configuration = Configuration()
            configuration.api_key['api-key'] = api_key

            api_client = ApiClient(configuration)
            api_instance = transactional_emails_api.TransactionalEmailsApi(api_client)

            mensagem_html = mensagem.replace("\n", "<br>")

            email = SendSmtpEmail(
                to=[{"email": destinatario}],
                subject=assunto,
                html_content=f"<html><body><p>{mensagem_html}</p></body></html>",
                sender={
                    "name": "Jefferson Cabeleireiro",
                    "email": "thalysondasilvaribeiro@gmail.com"
                }
            )


            api_instance.send_transac_email(email)
            print("Email enviado com sucesso!")

        except Exception as e:
            print("Erro ao enviar:", e)
    
    Thread(target=enviar, daemon=True).start()



@app.route("/mensagem-enviada")
def mensagem_enviada():
    return render_template("mensagem-enviada.html")


@app.route("/cancelar-agendamento/<int:id>")
def cancelar_agendamento(id):
    if "usuario_id" not in session:
        flash("Faça login primeiro", "erro")
        return redirect("/login")

    db = get_db_salao()
    cursor = db.cursor(dictionary=True)

    cursor.execute("""
        SELECT data, horario, usuario_id, email
        FROM agendamentos
        WHERE id=%s
    """, (id,))
    ag = cursor.fetchone()

    if not ag or ag["usuario_id"] != session["usuario_id"]:
        cursor.close()
        db.close()
        flash("Agendamento não encontrado", "erro")
        return redirect("/agendamentos")

    data_val = ag["data"]
    hora_val = ag["horario"]

    if hasattr(data_val, "strftime"):
        data_str = data_val.strftime("%Y-%m-%d")
    else:
        data_str = str(data_val)

    hora_str = str(hora_val)[:8]

    data_hora_agendamento = datetime.strptime(
        f"{data_str} {hora_str}",
        "%Y-%m-%d %H:%M:%S"
    )

    agora = datetime.utcnow() - timedelta(hours=3)

    if data_hora_agendamento - agora < timedelta(hours=24):
        cursor.close()
        db.close()
        flash("Cancelamento permitido apenas com 24 horas de antecedência.", "erro")
        return redirect("/agendamentos")

    mensagem_admin = f"""
Agendamento cancelado ❌

Cliente: {ag['email']}
📅 Data: {data_str}
⏰ Hora: {hora_str}
"""

    enviar_email(
        "thalysondasilvaribeiro@gmail.com",
        "Agendamento cancelado",
        mensagem_admin
    )

    cursor.execute("DELETE FROM agendamentos WHERE id=%s", (id,))
    db.commit()

    cursor.close()
    db.close()

    flash("Agendamento cancelado com sucesso.", "sucesso")
    return redirect("/agendamentos")

@app.route("/admin")
def admin():

    if "usuario_id" not in session:
        return redirect("/login")

    db_login = get_db_login()
    cursor_login = db_login.cursor(dictionary=True)

    cursor_login.execute(
        "SELECT is_admin FROM usuario WHERE codigo=%s",
        (session["usuario_id"],)
    )

    user = cursor_login.fetchone()

    cursor_login.close()
    db_login.close()

    if not user or user["is_admin"] != 1:
        return "Acesso negado"

    return render_template("admin.html")

@app.route("/admin/dia")
def admin_dia():

    if "usuario_id" not in session:
        return redirect("/login")

    hoje = datetime.now().strftime("%Y-%m-%d")

    db = get_db_salao()
    cursor = db.cursor(dictionary=True)

    # ================= LISTA CLIENTES =================
    cursor.execute("""
        SELECT *
        FROM agendamentos
        WHERE data=%s
        ORDER BY horario
    """, (hoje,))

    agendamentos = cursor.fetchall()

    # ================= RESUMO DO DIA =================
    cursor.execute("""
        SELECT
            SUM(valor_final) as total,
            SUM(CASE WHEN forma_pagamento='pix'
                THEN valor_final ELSE 0 END) as pix,
            SUM(CASE WHEN forma_pagamento='dinheiro'
                THEN valor_final ELSE 0 END) as dinheiro
        FROM agendamentos
        WHERE data=%s AND finalizado=1
    """, (hoje,))

    resumo = cursor.fetchone()

    # ✅ SÓ AGORA FECHA
    cursor.close()
    db.close()

    return render_template(
        "admin_dia.html",
        agendamentos=agendamentos,
        hoje=hoje,
        resumo=resumo
    )

@app.route("/admin/finalizar", methods=["POST"])
def finalizar_cliente():

    if "usuario_id" not in session:
        return redirect("/login")

    id_ag = request.form.get("id")
    pagamento = request.form.get("pagamento")
    valor = request.form.get("valor")

    db = get_db_salao()
    cursor = db.cursor()

    cursor.execute("""
        UPDATE agendamentos
        SET forma_pagamento=%s,
            valor_final=%s,
            finalizado=1
        WHERE id=%s
    """,(pagamento, valor, id_ag))

    db.commit()
    cursor.close()
    db.close()

    return redirect("/admin/dia")

if __name__ == "__main__":
    app.run()
