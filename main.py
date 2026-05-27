# =========================
# IMPORTAÇÕES
# =========================
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext
from datetime import datetime, timedelta, date
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
import uuid
import jwt
import os
import re
import unicodedata
import httpx
import resend
import base64
import json
import requests as http_requests

print("🔥 ENV DATABASE_URL:", os.getenv("DATABASE_URL"))

# =========================
# CONFIG
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("🚨 DATABASE_URL não encontrada!")

SECRET_KEY = "super_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440

resend.api_key = os.getenv("RESEND_API_KEY")

MICROSOFT_CLIENT_ID = os.getenv("MICROSOFT_CLIENT_ID")
MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET")
MICROSOFT_TENANT_ID = os.getenv("MICROSOFT_TENANT_ID")
MICROSOFT_REDIRECT_URI = os.getenv("MICROSOFT_REDIRECT_URI")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

BACKEND_URL = os.getenv("BACKEND_URL", "https://backend-crm-production-157b.up.railway.app")
OUTLOOK_WEBHOOK_SECRET = os.getenv("OUTLOOK_WEBHOOK_SECRET", "crm-webhook-secret")
GMAIL_PUBSUB_TOPIC = os.getenv("GMAIL_PUBSUB_TOPIC", "projects/SEU_PROJECT_ID/topics/gmail-crm-push")

engine = create_engine(DATABASE_URL)
security = HTTPBearer()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

SEGMENTOS_PADRAO = [
    "Academias e Fitness",
    "Administracao de Condominios",
    "Advocacia",
    "Agencia de Marketing",
    "Agencia de Publicidade",
    "Agronegocio",
    "Alimentos e Bebidas",
    "Arquitetura e Urbanismo",
    "Assistencia Tecnica",
    "Atacado e Distribuicao",
    "Automacao Industrial",
    "Autopecas",
    "Bares e Restaurantes",
    "Beleza e Estetica",
    "Biotecnologia",
    "Clinicas Medicas",
    "Comercio Exterior",
    "Comercio Varejista",
    "Concessionarias",
    "Construcao Civil",
    "Consultoria Empresarial",
    "Contabilidade",
    "Coworking",
    "Cursos e Treinamentos",
    "Decoracao",
    "Distribuidora",
    "E-commerce",
    "Educacao",
    "Energia",
    "Energia Solar",
    "Engenharia",
    "Entretenimento",
    "Escritorio de Projetos",
    "Eventos",
    "Farmacias e Drogarias",
    "Financeiro",
    "Franquias",
    "Gestao de Pessoas",
    "Hotelaria",
    "Imobiliarias",
    "Industria Alimenticia",
    "Industria Automotiva",
    "Industria Farmaceutica",
    "Industria Metalurgica",
    "Industria Textil",
    "Logistica e Transporte",
    "Manutencao Predial",
    "Maquinas e Equipamentos",
    "Materiais de Construcao",
    "Moda e Vestuario",
    "Moveis Planejados",
    "Odontologia",
    "Pet Shop",
    "Produtos Agropecuarios",
    "Recursos Humanos",
    "Saude",
    "Seguranca Eletronica",
    "Seguros",
    "Servicos de Limpeza",
    "Servicos Financeiros",
    "Software e SaaS",
    "Supermercados",
    "Tecnologia da Informacao",
    "Telecomunicacoes",
    "Turismo",
    "Venda de Gado",
    "Vendas B2B",
    "Veterinaria",
    "Agropecuaria",
    "Clinicas Odontologicas",
    "Confeitaria",
    "Delivery",
    "Grafica",
    "Hospitais",
    "Jardinagem e Paisagismo",
    "Laboratorios",
    "Laticinios",
    "Lavanderias",
    "Marcenaria",
    "Padarias",
    "Papelarias",
    "Postos de Combustivel",
    "Serralheria",
    "Transportadoras",
]

PALAVRAS_CHAVE_SEGMENTO = {
    "academia","administracao","advocacia","agencia","agro","agronegocio","alimento","arquitetura","assistencia","atacado","automacao",
    "autopecas","bar","beleza","biotecnologia","clinica","comercio","condominio","concessionaria","construcao","consultoria","contabilidade","coworking",
    "curso","decoracao","distribuicao","distribuidora","ecommerce","educacao","energia","engenharia","entretenimento","escola",
    "evento","farmacia","financeiro","fitness","franquia","gado","gestao","hotel","imobiliaria","industria","limpeza","logistica",
    "manutencao","maquinas","marketing","materiais","medica","metalurgica","moda","moveis","odontologia","oficina","papelaria","pet",
    "projetos","publicidade","recursos","restaurante","rh","saas","saude",
    "seguranca",
    "seguros",
    "servicos",
    "software",
    "solar",
    "supermercado",
    "tecnologia",
    "telecomunicacoes",
    "textil",
    "transporte",
    "turismo",
    "varejo",
    "vendas",
    "veterinaria",
    "agropecuaria",
    "combustivel",
    "confeitaria",
    "contabil",
    "delivery",
    "frigorifico",
    "grafica",
    "hospital",
    "jardinagem",
    "juridico",
    "laboratorio",
    "laticinios",
    "lavanderia",
    "marcenaria",
    "padaria",
    "paisagismo",
    "panificadora",
    "pecuaria",
    "posto",
    "rural",
    "serralheria",
    "transportadora",
}

# =========================
# SEGURANÇA
# =========================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_senha(senha: str) -> str:
    return pwd_context.hash(senha[:72])


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return pwd_context.verify(senha[:72], senha_hash)


def criar_token_acesso(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email:
            raise HTTPException(401, "Token inválido")
        return email
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token inválido")


# =========================
# EMAIL (Resend)
# =========================
async def enviar_email(destino: str, token: str):
    link = f"https://frontend-crm-xi-plum.vercel.app/ativar?token={token}"
    resend.Emails.send(
        {
            "from": "onboarding@resend.dev",
            "to": destino,
            "subject": "Ative sua conta 🚀",
            "html": f"<p>Olá!</p><p>Clique no link abaixo para criar sua senha:</p><p><a href='{link}'>{link}</a></p>",
        }
    )


# =========================
# MODELOS
# =========================
class UsuarioCreate(BaseModel):
    nome: str
    email: EmailStr
    telefone: str | None = None


class UsuarioUpdate(BaseModel):
    nome: str | None = None
    telefone: str | None = None
    cargo: str | None = None
    empresa_nome: str | None = None
    bio: str | None = None


class EmpresaCreate(BaseModel):
    nome: str
    segmento: str | None = None
    porte: str | None = None
    cidade: str | None = None
    endereco: str | None = None
    cep: str | None = None
    bairro: str | None = None
    regiao: str | None = None
    observacoes: str | None = None
    cnpj: str | None = None
    site: str | None = None
    linkedin_empresa: str | None = None
    responsavel_principal: str | None = None
    ticket_medio_estimado: float | None = None
    status: str | None = None
    origem_lead: str | None = None
    ultima_interacao: datetime | None = None
    proxima_acao: str | None = None
    data_proxima_acao: date | None = None
    motivo_perdido: str | None = None
    temperatura: str | None = None


class EmpresaUpdate(BaseModel):
    nome: str | None = None
    segmento: str | None = None
    porte: str | None = None
    cidade: str | None = None
    endereco: str | None = None
    cep: str | None = None
    bairro: str | None = None
    regiao: str | None = None
    observacoes: str | None = None
    cnpj: str | None = None
    site: str | None = None
    linkedin_empresa: str | None = None
    responsavel_principal: str | None = None
    ticket_medio_estimado: float | None = None
    status: str | None = None
    origem_lead: str | None = None
    ultima_interacao: datetime | None = None
    proxima_acao: str | None = None
    data_proxima_acao: date | None = None
    motivo_perdido: str | None = None
    temperatura: str | None = None


class SegmentoCreate(BaseModel):
    nome: str


class EventoCreate(BaseModel):
    titulo: str
    tipo: str
    data: date
    hora_inicio: str
    hora_fim: Optional[str] = None
    empresa_id: Optional[str] = None
    empresa_nome: Optional[str] = None
    descricao: Optional[str] = None


class EventoUpdate(BaseModel):
    titulo: str | None = None
    tipo: str | None = None
    data: date | None = None
    hora_inicio: str | None = None
    hora_fim: str | None = None
    empresa_id: str | None = None
    empresa_nome: str | None = None
    descricao: str | None = None


class AtivarConta(BaseModel):
    token: str
    senha: str


class Login(BaseModel):
    email: EmailStr
    senha: str


class Token(BaseModel):
    access_token: str
    token_type: str


class ContatoUpdate(BaseModel):
    nome: str | None = None
    funcao: str | None = None
    email: str | None = None
    celular: str | None = None
    whatsapp: str | None = None
    linkedin: str | None = None
    observacoes: str | None = None
    prioridade: str | None = None
    nivel_influencia: str | None = None
    decisor: bool | None = None
    canal_preferido: str | None = None
    data_ultimo_contato: date | None = None


class ReuniaoOutlook(BaseModel):
    titulo: str
    descricao: Optional[str] = None
    data: date
    hora_inicio: str
    hora_fim: str
    email_convidado: Optional[str] = None


class ReuniaoGoogle(BaseModel):
    titulo: str
    descricao: Optional[str] = None
    data: date
    hora_inicio: str
    hora_fim: str
    email_convidado: Optional[str] = None


# =========================
# SEGMENTOS (helpers)
# =========================
def normalizar_texto(valor: str) -> str:
    sem_acentos = unicodedata.normalize("NFD", valor.lower())
    sem_acentos = "".join(ch for ch in sem_acentos if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", sem_acentos).strip()


def limpar_segmento(nome: str) -> str:
    return re.sub(r"\s+", " ", nome.strip())[:120]


def segmento_valido(nome: str) -> bool:
    nome_limpo = limpar_segmento(nome)
    normalizado = normalizar_texto(nome_limpo)
    if len(normalizado) < 3 or not re.search(r"[a-z]", normalizado):
        return False
    segmentos_base = {normalizar_texto(segmento) for segmento in SEGMENTOS_PADRAO}
    if normalizado in segmentos_base:
        return True
    palavras = set(re.findall(r"[a-z0-9]+", normalizado))
    return bool(palavras & PALAVRAS_CHAVE_SEGMENTO)


def garantir_tabela_segmentos(conn):
    conn.execute(
        text(
            """
        CREATE TABLE IF NOT EXISTS segmentos (
            segmento_id uuid PRIMARY KEY,
            nome character varying(120) NOT NULL,
            nome_normalizado character varying(120) UNIQUE NOT NULL,
            criado_em timestamp without time zone DEFAULT CURRENT_TIMESTAMP
        )
    """
        )
    )
    for segmento in SEGMENTOS_PADRAO:
        nome = limpar_segmento(segmento)
        conn.execute(
            text(
                """
                INSERT INTO segmentos (segmento_id, nome, nome_normalizado)
                VALUES (:id, :nome, :nome_normalizado)
                ON CONFLICT (nome_normalizado) DO NOTHING
            """
            ),
            {"id": str(uuid.uuid4()), "nome": nome, "nome_normalizado": normalizar_texto(nome)},
        )


def salvar_segmento(conn, nome: str) -> str:
    nome_limpo = limpar_segmento(nome)
    if not segmento_valido(nome_limpo):
        raise HTTPException(400, "Segmento nao reconhecido.")
    garantir_tabela_segmentos(conn)
    conn.execute(
        text(
            """
            INSERT INTO segmentos (segmento_id, nome, nome_normalizado)
            VALUES (:id, :nome, :nome_normalizado)
            ON CONFLICT (nome_normalizado) DO UPDATE SET nome = EXCLUDED.nome
        """
        ),
        {"id": str(uuid.uuid4()), "nome": nome_limpo, "nome_normalizado": normalizar_texto(nome_limpo)},
    )
    return nome_limpo


def garantir_campos_pipeline(conn):
    conn.execute(text("ALTER TABLE empresas ADD COLUMN IF NOT EXISTS data_proxima_acao date"))
    conn.execute(
        text(
            "ALTER TABLE empresas ADD COLUMN IF NOT EXISTS status_atualizado_em timestamp without time zone DEFAULT CURRENT_TIMESTAMP"
        )
    )
    conn.execute(text("ALTER TABLE empresas ADD COLUMN IF NOT EXISTS motivo_perdido text"))
    conn.execute(
        text(
            """
        CREATE TABLE IF NOT EXISTS empresa_status_historico (
            historico_id uuid PRIMARY KEY,
            empresa_id uuid NOT NULL,
            status_anterior character varying(50),
            status_novo character varying(50) NOT NULL,
            observacao text,
            alterado_em timestamp without time zone DEFAULT CURRENT_TIMESTAMP
        )
    """
        )
    )


def garantir_colunas_oauth(conn):
    conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS outlook_access_token text"))
    conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS outlook_refresh_token text"))
    conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS google_access_token text"))
    conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS google_refresh_token text"))


def garantir_tabela_notificacoes(conn):
    conn.execute(
        text(
            """
        CREATE TABLE IF NOT EXISTS notificacoes (
            notificacao_id UUID PRIMARY KEY,
            usuario_email TEXT NOT NULL,
            tipo TEXT NOT NULL,
            titulo TEXT NOT NULL,
            mensagem TEXT NOT NULL,
            empresa_id UUID NULL,
            empresa_nome TEXT NULL,
            platform TEXT NULL,
            meta JSONB DEFAULT '{}'::jsonb,
            lida BOOLEAN DEFAULT FALSE,
            criado_em TIMESTAMP DEFAULT NOW()
        )
    """
        )
    )
    conn.execute(text("ALTER TABLE notificacoes ADD COLUMN IF NOT EXISTS platform VARCHAR(30)"))
    conn.execute(text("ALTER TABLE notificacoes ADD COLUMN IF NOT EXISTS meta JSONB DEFAULT '{}'"))
    conn.execute(
        text(
            """
        CREATE TABLE IF NOT EXISTS email_subscriptions (
            sub_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            usuario_email TEXT NOT NULL,
            provider VARCHAR(20) NOT NULL,
            subscription_id TEXT,
            email_address TEXT,
            history_id BIGINT,
            expires_at TIMESTAMP,
            access_token TEXT,
            refresh_token TEXT,
            criado_em TIMESTAMP DEFAULT NOW(),
            atualizado_em TIMESTAMP DEFAULT NOW()
        )
    """
        )
    )
    conn.execute(text("ALTER TABLE eventos ADD COLUMN IF NOT EXISTS outlook_event_id TEXT"))
    conn.execute(text("ALTER TABLE eventos ADD COLUMN IF NOT EXISTS google_event_id TEXT"))


# =========================
# JOB: RASCUNHOS EXPIRÁVEIS
# =========================
def verificar_rascunhos_expirados():
    print("⏰ JOB: verificando rascunhos expirados...")
    try:
        with engine.begin() as conn:
            garantir_tabela_notificacoes(conn)

            agora = datetime.utcnow()
            limite_aviso = agora - timedelta(days=25)
            limite_exclusao = agora - timedelta(days=30)

            # Rascunhos com 25-29 dias → aviso
            avisos = conn.execute(
                text(
                    """
                SELECT e.empresa_id, e.nome, e.status_atualizado_em, u.email
                FROM empresas e
                JOIN usuarios u ON u.ativo = TRUE
                WHERE e.status = 'Rascunho'
                  AND e.status_atualizado_em <= :limite_aviso
                  AND e.status_atualizado_em > :limite_exclusao
            """
                ),
                {"limite_aviso": limite_aviso, "limite_exclusao": limite_exclusao},
            ).fetchall()

            for r in avisos:
                dias_restantes = 30 - int((agora - r.status_atualizado_em).days)
                existe = conn.execute(
                    text(
                        """
                    SELECT 1 FROM notificacoes
                    WHERE empresa_id = :eid AND tipo = 'rascunho_aviso'
                      AND criado_em >= NOW() - INTERVAL '23 hours'
                """
                    ),
                    {"eid": r.empresa_id},
                ).fetchone()
                if not existe:
                    conn.execute(
                        text(
                            """
                        INSERT INTO notificacoes
                            (notificacao_id, usuario_email, tipo, titulo, mensagem, empresa_id, empresa_nome)
                        VALUES (:id, :email, 'rascunho_aviso', :titulo, :mensagem, :eid, :enome)
                    """
                        ),
                        {
                            "id": str(uuid.uuid4()),
                            "email": r.email,
                            "titulo": f"Rascunho expira em {dias_restantes} dia{'s' if dias_restantes != 1 else ''}",
                            "mensagem": f"O rascunho '{r.nome}' será excluído automaticamente em {dias_restantes} dia{'s' if dias_restantes != 1 else ''}. Complete o cadastro para não perder.",
                            "eid": r.empresa_id,
                            "enome": r.nome,
                        },
                    )
                    print(f"📢 Aviso gerado para rascunho: {r.nome}")

            # Rascunhos com 30+ dias → excluir
            expirados = conn.execute(
                text(
                    """
                SELECT e.empresa_id, e.nome, u.email
                FROM empresas e
                JOIN usuarios u ON u.ativo = TRUE
                WHERE e.status = 'Rascunho'
                  AND e.status_atualizado_em <= :limite_exclusao
            """
                ),
                {"limite_exclusao": limite_exclusao},
            ).fetchall()

            for r in expirados:
                conn.execute(
                    text(
                        """
                    INSERT INTO notificacoes
                        (notificacao_id, usuario_email, tipo, titulo, mensagem, empresa_id, empresa_nome)
                    VALUES (:id, :email, 'rascunho_excluido', :titulo, :mensagem, :eid, :enome)
                """
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "email": r.email,
                        "titulo": "Rascunho excluído automaticamente",
                        "mensagem": f"O rascunho '{r.nome}' foi excluído por inatividade após 30 dias. Cadastre novamente se necessário.",
                        "eid": r.empresa_id,
                        "enome": r.nome,
                    },
                )
                conn.execute(text("DELETE FROM contatos WHERE empresa_id = :id"), {"id": r.empresa_id})
                conn.execute(text("DELETE FROM empresa_status_historico WHERE empresa_id = :id"), {"id": r.empresa_id})
                conn.execute(text("DELETE FROM empresas WHERE empresa_id = :id"), {"id": r.empresa_id})
                print(f"🗑️ Rascunho excluído: {r.nome}")

        print("✅ JOB: verificação de rascunhos concluída")
    except Exception as e:
        print(f"🔴 JOB ERRO: {str(e)}")


# =========================
# WEBHOOK HELPERS
# =========================

# Padrões de remetentes automáticos a ignorar
BLOCKED_SENDER_PATTERNS = [
    "noreply",
    "no-reply",
    "no_reply",
    "donotreply",
    "do-not-reply",
    "mailer-daemon",
    "postmaster",
    "bounce",
    "bounces",
    "notifications@",
    "notify@",
    "alert@",
    "alerts@",
    "system@",
    "auto@",
    "automated@",
    "autoresponder",
    "support@",
    "helpdesk@",
    "feedback@",
    "unsubscribe",
    "newsletter",
    "news@",
    "info@noreply",
    "microsoft@",
    "google@",
    "amazonses",
    "sendgrid",
    "mailchimp",
    "hubspot",
    "salesforce",
]


def is_automated_sender(email: str) -> bool:
    """Retorna True se o remetente parecer automático/noreply."""
    email_lower = email.lower()
    return any(pattern in email_lower for pattern in BLOCKED_SENDER_PATTERNS)


def find_company_by_sender(conn, sender_email: str):
    results = conn.execute(
        text(
            """
        SELECT
            c.empresa_id,
            c.contato_id,
            e.nome as empresa_nome,
            c.data_ultimo_contato,
            e.ultima_interacao
        FROM contatos c
        JOIN empresas e
            ON e.empresa_id = c.empresa_id
        WHERE LOWER(c.email) = LOWER(:email)
        ORDER BY
            c.decisor DESC NULLS LAST,
            c.data_ultimo_contato DESC NULLS LAST,
            e.ultima_interacao DESC NULLS LAST
        LIMIT 1
    """
        ),
        {"email": sender_email.strip()},
    ).fetchone()

    if results:
        return (
            results._mapping["empresa_id"],
            results._mapping["contato_id"],
            results._mapping["empresa_nome"],
        )

    return None, None, None


def create_interaction_notification(
    conn,
    usuario_email: str,
    empresa_id,
    empresa_nome: str,
    platform: str,
    sender_name: str,
    sender_email: str,
    subject: str,
    conversation_id: str = "",
):
    cutoff = datetime.utcnow() - timedelta(minutes=1)
    existe = conn.execute(
        text(
            """
        SELECT 1 FROM notificacoes
        WHERE empresa_id = :eid AND tipo = 'email_interaction' AND platform = :platform
          AND meta->>'sender_email' = :semail
          AND criado_em >= :cutoff
    """
        ),
        {"eid": str(empresa_id), "platform": platform, "semail": sender_email, "cutoff": cutoff},
    ).fetchone()
    if existe:
        return

    label = "Gmail" if platform == "gmail" else "Outlook"
    conn.execute(
        text(
            """
        INSERT INTO notificacoes
            (notificacao_id, usuario_email, tipo, titulo, mensagem,
             empresa_id, empresa_nome, platform, meta, lida, criado_em)
        VALUES
            (:id, :email, 'email_interaction', :titulo, :mensagem,
             :eid, :enome, :platform, CAST(:meta AS JSONB), FALSE, NOW())
    """
        ),
        {
            "id": str(uuid.uuid4()),
            "email": usuario_email,
            "titulo": empresa_nome,
            "mensagem": f"Nova interação via {label}",
            "eid": str(empresa_id),
            "enome": empresa_nome,
            "platform": platform,
            "meta": json.dumps(
                {
                    "sender_email": sender_email,
                    "sender_name": sender_name,
                    "subject": subject,
                    "conversation_id": conversation_id,
                }
            ),
        },
    )


# =========================
# GMAIL WATCH
# =========================
def setup_gmail_watch(usuario_email: str, access_token: str, refresh_token: str, gmail_address: str):
    try:
        res = http_requests.post(
            f"https://gmail.googleapis.com/gmail/v1/users/{gmail_address}/watch",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={"topicName": GMAIL_PUBSUB_TOPIC, "labelIds": ["INBOX"]},
            timeout=15,
        )
        if not res.ok:
            print(f"[Gmail Watch] Erro: {res.text}")
            return
        data = res.json()
        history_id = int(data.get("historyId", 0))
        expires_ms = int(data.get("expiration", 0))
        expires_at = datetime.utcfromtimestamp(expires_ms / 1000) if expires_ms else None
        with engine.begin() as conn:
            garantir_tabela_notificacoes(conn)
            existing = conn.execute(
                text(
                    """
                SELECT sub_id FROM email_subscriptions
                WHERE usuario_email = :email AND provider = 'gmail'
            """
                ),
                {"email": usuario_email},
            ).fetchone()
            if existing:
                conn.execute(
                    text(
                        """
                    UPDATE email_subscriptions
                    SET history_id=:hid, expires_at=:exp, access_token=:at,
                        refresh_token=:rt, email_address=:addr, atualizado_em=NOW()
                    WHERE usuario_email=:email AND provider='gmail'
                """
                    ),
                    {
                        "hid": history_id,
                        "exp": expires_at,
                        "at": access_token,
                        "rt": refresh_token,
                        "addr": gmail_address,
                        "email": usuario_email,
                    },
                )
            else:
                conn.execute(
                    text(
                        """
                    INSERT INTO email_subscriptions
                        (sub_id, usuario_email, provider, email_address, history_id,
                         expires_at, access_token, refresh_token)
                    VALUES (:id, :email, 'gmail', :addr, :hid, :exp, :at, :rt)
                """
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "email": usuario_email,
                        "addr": gmail_address,
                        "hid": history_id,
                        "exp": expires_at,
                        "at": access_token,
                        "rt": refresh_token,
                    },
                )
        print(f"[Gmail Watch] OK para {gmail_address}, historyId={history_id}")
    except Exception as e:
        print(f"[Gmail Watch] Exceção: {e}")


# =========================
# OUTLOOK EMAIL SUBSCRIPTION
# =========================
def setup_outlook_subscription(usuario_email: str, access_token: str, refresh_token: str):
    try:
        expires_at = datetime.utcnow() + timedelta(minutes=4000)
        res = http_requests.post(
            "https://graph.microsoft.com/v1.0/subscriptions",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={
                "changeType": "created",
                "notificationUrl": f"{BACKEND_URL}/webhooks/outlook",
                "resource": "me/mailFolders('Inbox')/messages",
                "expirationDateTime": expires_at.strftime("%Y-%m-%dT%H:%M:%S.0000000Z"),
                "clientState": OUTLOOK_WEBHOOK_SECRET,
            },
            timeout=15,
        )
        if not res.ok:
            print(f"[Outlook Sub] Erro: {res.text}")
            return
        sub_id = res.json().get("id")
        me_res = http_requests.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        email_address = me_res.json().get("mail") or me_res.json().get("userPrincipalName", "")
        with engine.begin() as conn:
            garantir_tabela_notificacoes(conn)
            existing = conn.execute(
                text(
                    """
                SELECT sub_id FROM email_subscriptions
                WHERE usuario_email = :email AND provider = 'outlook'
            """
                ),
                {"email": usuario_email},
            ).fetchone()
            if existing:
                conn.execute(
                    text(
                        """
                    UPDATE email_subscriptions
                    SET subscription_id=:sid, expires_at=:exp, access_token=:at,
                        refresh_token=:rt, email_address=:addr, atualizado_em=NOW()
                    WHERE usuario_email=:email AND provider='outlook'
                """
                    ),
                    {
                        "sid": sub_id,
                        "exp": expires_at,
                        "at": access_token,
                        "rt": refresh_token,
                        "addr": email_address,
                        "email": usuario_email,
                    },
                )
            else:
                conn.execute(
                    text(
                        """
                    INSERT INTO email_subscriptions
                        (sub_id, usuario_email, provider, subscription_id,
                         email_address, expires_at, access_token, refresh_token)
                    VALUES (:id, :email, 'outlook', :sid, :addr, :exp, :at, :rt)
                """
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "email": usuario_email,
                        "sid": sub_id,
                        "addr": email_address,
                        "exp": expires_at,
                        "at": access_token,
                        "rt": refresh_token,
                    },
                )
        print(f"[Outlook Sub] OK para {email_address}, id={sub_id}")
    except Exception as e:
        print(f"[Outlook Sub] Exceção: {e}")


# =========================
# OUTLOOK CALENDAR SUBSCRIPTION
# =========================
def setup_outlook_calendar_subscription(usuario_email: str, access_token: str, refresh_token: str):
    try:
        expires_at = datetime.utcnow() + timedelta(minutes=4000)
        res = http_requests.post(
            "https://graph.microsoft.com/v1.0/subscriptions",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json={
                "changeType": "updated",
                "notificationUrl": f"{BACKEND_URL}/webhooks/outlook-calendar",
                "resource": "me/events",
                "expirationDateTime": expires_at.strftime("%Y-%m-%dT%H:%M:%S.0000000Z"),
                "clientState": OUTLOOK_WEBHOOK_SECRET,
            },
            timeout=15,
        )
        if not res.ok:
            print(f"[Outlook Cal Sub] Erro: {res.text}")
            return
        sub_id = res.json().get("id")
        with engine.begin() as conn:
            garantir_tabela_notificacoes(conn)
            existing = conn.execute(
                text(
                    """
                SELECT sub_id FROM email_subscriptions
                WHERE usuario_email = :email AND provider = 'outlook_calendar'
            """
                ),
                {"email": usuario_email},
            ).fetchone()
            if existing:
                conn.execute(
                    text(
                        """
                    UPDATE email_subscriptions
                    SET subscription_id=:sid, expires_at=:exp, access_token=:at,
                        refresh_token=:rt, atualizado_em=NOW()
                    WHERE usuario_email=:email AND provider='outlook_calendar'
                """
                    ),
                    {"sid": sub_id, "exp": expires_at, "at": access_token, "rt": refresh_token, "email": usuario_email},
                )
            else:
                conn.execute(
                    text(
                        """
                    INSERT INTO email_subscriptions
                        (sub_id, usuario_email, provider, subscription_id,
                         expires_at, access_token, refresh_token)
                    VALUES (:id, :email, 'outlook_calendar', :sid, :exp, :at, :rt)
                """
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "email": usuario_email,
                        "sid": sub_id,
                        "exp": expires_at,
                        "at": access_token,
                        "rt": refresh_token,
                    },
                )
        print(f"[Outlook Cal Sub] OK para {usuario_email}, id={sub_id}")
    except Exception as e:
        print(f"[Outlook Cal Sub] Exceção: {e}")


# =========================
# WEBHOOKS
# =========================

@app.post("/webhooks/gmail", include_in_schema=False)
async def gmail_webhook(request: Request):
    try:
        body = await request.json()
    except Exception:
        return {"ok": True}

    msg_data = body.get("message", {}).get("data", "")
    if not msg_data:
        return {"ok": True}

    try:
        decoded = json.loads(base64.b64decode(msg_data).decode("utf-8"))
        gmail_addr = decoded.get("emailAddress", "")
        new_hist = int(decoded.get("historyId", 0))
    except Exception as e:
        print(f"[Gmail Webhook] Decode erro: {e}")
        return {"ok": True}

    with engine.begin() as conn:
        garantir_tabela_notificacoes(conn)
        sub = conn.execute(
            text(
                """
            SELECT * FROM email_subscriptions
            WHERE provider='gmail' AND email_address=:addr
        """
            ),
            {"addr": gmail_addr},
        ).fetchone()
        if not sub:
            return {"ok": True}

        sub = dict(sub._mapping)
        old_hist = sub.get("history_id") or new_hist
        access_token = sub.get("access_token", "")
        usuario_email = sub.get("usuario_email", "")

        if new_hist <= old_hist:
            return {"ok": True}

        conn.execute(
            text(
                """
            UPDATE email_subscriptions SET history_id=:hid, atualizado_em=NOW()
            WHERE provider='gmail' AND email_address=:addr
        """
            ),
            {"hid": new_hist, "addr": gmail_addr},
        )

    hist_res = http_requests.get(
        f"https://gmail.googleapis.com/gmail/v1/users/{gmail_addr}/history"
        f"?startHistoryId={old_hist}&labelId=INBOX",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    if not hist_res.ok:
        return {"ok": True}

    for record in hist_res.json().get("history", []):

        entries = []

        entries.extend(record.get("messagesAdded", []))

        for msg in record.get("messages", []):
            entries.append({"message": msg})

        for entry in entries:

            msg_id = entry.get("message", {}).get("id")

            if not msg_id:
                continue

            msg_res = http_requests.get(
                f"https://gmail.googleapis.com/gmail/v1/users/{gmail_addr}/messages/{msg_id}"
                "?format=full",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10,
            )

            if not msg_res.ok:
                print("[GMAIL] erro ao buscar mensagem")
                continue

            msg_json = msg_res.json()

            headers_map = {
                h["name"].lower(): h["value"]
                for h in msg_json.get("payload", {}).get("headers", [])
            }

            print("[GMAIL] headers:", headers_map)

            thread_id = msg_json.get("threadId", "")

            from_raw = headers_map.get("from", "")
            subject = headers_map.get("subject", "")
            in_reply = headers_map.get("in-reply-to", "")

            subject_clean = (subject or "").strip().lower()

            reply_prefixes = (
            "re:",
            "res:",
            "aw:",
            "fw:",
            "fwd:",
            "aceito:",
            "accepted:",
            "recusado:",
            "declined:",
            "talvez:",
            "tentative:"
        )

            is_reply = (
                bool(in_reply)
                or subject_clean.startswith(reply_prefixes)
            )

            print("[GMAIL] subject:", subject)
            print("[GMAIL] in_reply:", in_reply)
            print("[GMAIL] is_reply:", is_reply)

            if not is_reply:
                print("[GMAIL] ignorado - não é reply")
                continue

            match = re.match(
                r"^(.*?)\s*<(.+?)>$",
                from_raw.strip()
            )

            sender_name = (
                match.group(1).strip().strip('"')
                if match else ""
            )

            sender_email = (
                match.group(2).strip()
                if match else from_raw.strip()
            )

            print("[GMAIL] sender_email:", sender_email)

            is_calendar_response = subject.lower().startswith(
                (
                    "aceito:",
                    "accepted:",
                    "recusado:",
                    "declined:",
                    "talvez:",
                    "tentative:"
                )
            )

            if (
                sender_email.lower() == gmail_addr.lower()
                and not is_calendar_response
            ):
                print("[GMAIL] ignorado - meu próprio email")
                continue

            if is_automated_sender(sender_email):
                print("[GMAIL] ignorado - remetente automático")
                continue

            with engine.begin() as conn:
                
                if is_calendar_response:
                    print("[GMAIL] calendar response detectada")

                    evento = conn.execute(
                        text("""
                            SELECT empresa_id, empresa_nome
                            FROM eventos
                            WHERE google_event_id IS NOT NULL
                            AND usuario_email = :email
                            ORDER BY criado_em DESC
                            LIMIT 1
                        """),
                        {"email": usuario_email},
                    ).fetchone()

                    if evento:
                        empresa_id = evento.empresa_id
                        empresa_nome = evento.empresa_nome

                        print(
                            "[GMAIL] criando notificação calendário:",
                            empresa_nome
                        )

                        create_interaction_notification(
                            conn,
                            usuario_email,
                            empresa_id,
                            empresa_nome,
                            "gmail",
                            "Resposta calendário",
                            sender_email,
                            subject,
                            thread_id,
                        )

                    continue

                empresa_id, _, empresa_nome = find_company_by_sender(
                    conn,
                    sender_email
                )

                print(
                    "[GMAIL] empresa encontrada:",
                    empresa_id,
                    empresa_nome
                )

                if empresa_id:
                    print("[GMAIL] criando notificação")

                    create_interaction_notification(
                        conn,
                        usuario_email,
                        empresa_id,
                        empresa_nome,
                        "gmail",
                        sender_name,
                        sender_email,
                        subject,
                        thread_id,
                    )

    return {"ok": True}


@app.api_route("/webhooks/outlook", methods=["GET", "POST"], include_in_schema=False)
async def outlook_webhook(request: Request):
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        from fastapi.responses import PlainTextResponse

        return PlainTextResponse(content=validation_token, status_code=200)

    try:
        body = await request.json()
    except Exception:
        return {"ok": True}

    for notif in body.get("value", []):
        if notif.get("clientState") != OUTLOOK_WEBHOOK_SECRET:
            continue
        sub_id = notif.get("subscriptionId")
        msg_id = notif.get("resourceData", {}).get("id")
        if not msg_id:
            continue

        with engine.begin() as conn:
            garantir_tabela_notificacoes(conn)
            sub = conn.execute(
                text(
                    """
                SELECT * FROM email_subscriptions
                WHERE provider='outlook' AND subscription_id=:sid
            """
                ),
                {"sid": sub_id},
            ).fetchone()
            if not sub:
                continue
            sub = dict(sub._mapping)

        access_token = sub.get("access_token", "")
        usuario_email = sub.get("usuario_email", "")
        own_email = sub.get("email_address", "")

        # Busca mensagem com cabeçalhos de resposta para detectar replies reais
        msg_res = http_requests.get(
            f"https://graph.microsoft.com/v1.0/me/messages/{msg_id}"
            "?$select=from,subject,conversationId,internetMessageHeaders",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if not msg_res.ok:
            continue

        msg_data = msg_res.json()
        from_obj = msg_data.get("from", {}).get("emailAddress", {})
        sender_email = from_obj.get("address", "")
        sender_name = from_obj.get("name", "")
        subject = msg_data.get("subject", "")
        conversation_id = msg_data.get("conversationId", "")

        # Verifica se é uma resposta real via cabeçalhos Internet padrão
        internet_headers = {
            h.get("name", "").lower(): h.get("value", "")
            for h in msg_data.get("internetMessageHeaders", [])
        }

        in_reply_to = internet_headers.get("in-reply-to", "")

        subject_clean = (subject or "").strip().lower()

        reply_prefixes = (
            "re:",
            "res:",
            "aw:",
            "fw:",
            "fwd:",
        )

        is_reply = bool(in_reply_to) or subject_clean.startswith(reply_prefixes)

        if not is_reply:
            print(f"[Outlook Webhook] Ignorado (não é reply): {subject}")
            continue

        if not sender_email:
            continue
        if sender_email.lower() == own_email.lower():
            continue
        if is_automated_sender(sender_email):
            print(f"[Outlook Webhook] Ignorado (remetente automático): {sender_email}")
            continue

        with engine.begin() as conn:
            empresa_id, _, empresa_nome = find_company_by_sender(conn, sender_email)
            if empresa_id:
                create_interaction_notification(
                    conn,
                    usuario_email,
                    empresa_id,
                    empresa_nome,
                    "outlook",
                    sender_name,
                    sender_email,
                    subject,
                    conversation_id,
                )

    return {"ok": True}


@app.api_route("/webhooks/outlook-calendar", methods=["GET", "POST"], include_in_schema=False)
async def outlook_calendar_webhook(request: Request):
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        from fastapi.responses import PlainTextResponse

        return PlainTextResponse(content=validation_token, status_code=200)

    try:
        body = await request.json()
    except Exception:
        return {"ok": True}

    for notif in body.get("value", []):
        if notif.get("clientState") != OUTLOOK_WEBHOOK_SECRET:
            continue
        sub_id = notif.get("subscriptionId")
        event_id = notif.get("resourceData", {}).get("id")
        if not event_id:
            continue

        with engine.begin() as conn:
            garantir_tabela_notificacoes(conn)
            sub = conn.execute(
                text(
                    """
                SELECT * FROM email_subscriptions
                WHERE provider='outlook_calendar' AND subscription_id=:sid
            """
                ),
                {"sid": sub_id},
            ).fetchone()
            if not sub:
                continue
            sub = dict(sub._mapping)

        access_token = sub.get("access_token", "")
        usuario_email = sub.get("usuario_email", "")

        event_res = http_requests.get(
            f"https://graph.microsoft.com/v1.0/me/events/{event_id}?$select=subject,attendees",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        if not event_res.ok:
            continue

        event_data = event_res.json()
        subject = event_data.get("subject", "")
        attendees = event_data.get("attendees", [])

        with engine.begin() as conn:
            evento = conn.execute(
                text(
                    """
                SELECT evento_id, empresa_id, empresa_nome, titulo
                FROM eventos
                WHERE outlook_event_id = :eid AND usuario_email = :uemail
            """
                ),
                {"eid": event_id, "uemail": usuario_email},
            ).fetchone()
            if not evento:
                continue

            evento = dict(evento._mapping)
            empresa_id = evento.get("empresa_id")
            empresa_nome = evento.get("empresa_nome")
            titulo_evento = evento.get("titulo", subject)
            if not empresa_id or not empresa_nome:
                continue

            response_map = {
                "accepted": ("calendar_accepted", "aceitou"),
                "declined": ("calendar_declined", "recusou"),
                "tentativelyAccepted": ("calendar_tentative", "disse talvez para"),
            }

            for attendee in attendees:
                response = attendee.get("status", {}).get("response", "")
                email_addr = attendee.get("emailAddress", {}).get("address", "")
                name = attendee.get("emailAddress", {}).get("name", email_addr)

                if response not in response_map:
                    continue

                notif_tipo, verbo = response_map[response]

                existe = conn.execute(
                    text(
                        """
                    SELECT 1 FROM notificacoes
                    WHERE empresa_id = :eid
                      AND tipo = :tipo
                      AND meta->>'attendee_email' = :aemail
                      AND meta->>'outlook_event_id' = :evid
                """
                    ),
                    {
                        "eid": str(empresa_id),
                        "tipo": notif_tipo,
                        "aemail": email_addr,
                        "evid": event_id,
                    },
                ).fetchone()
                if existe:
                    continue

                conn.execute(
                    text(
                        """
                    INSERT INTO notificacoes
                        (notificacao_id, usuario_email, tipo, titulo, mensagem,
                         empresa_id, empresa_nome, platform, meta, lida, criado_em)
                    VALUES
                        (:id, :uemail, :tipo, :titulo, :mensagem,
                         :eid, :enome, 'outlook', CAST(:meta AS JSONB), FALSE, NOW())
                """
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "uemail": usuario_email,
                        "tipo": notif_tipo,
                        "titulo": f"{empresa_nome} {verbo} a call",
                        "mensagem": f"{name} {verbo} o convite para '{titulo_evento}'.",
                        "eid": str(empresa_id),
                        "enome": empresa_nome,
                        "meta": json.dumps(
                            {
                                "attendee_email": email_addr,
                                "attendee_name": name,
                                "outlook_event_id": event_id,
                                "event_subject": subject,
                            }
                        ),
                    },
                )

    return {"ok": True}


# =========================
# RENOVAÇÃO DE SUBSCRIPTIONS
# =========================
def renovar_gmail_watches():
    with engine.begin() as conn:
        garantir_tabela_notificacoes(conn)
        subs = conn.execute(
            text(
                """
            SELECT * FROM email_subscriptions
            WHERE provider='gmail'
              AND (expires_at IS NULL OR expires_at <= NOW() + INTERVAL '36 hours')
        """
            )
        ).fetchall()
    for sub in subs:
        s = dict(sub._mapping)
        setup_gmail_watch(
            s["usuario_email"],
            s.get("access_token", ""),
            s.get("refresh_token", ""),
            s.get("email_address", ""),
        )


def renovar_outlook_subscriptions():
    with engine.begin() as conn:
        garantir_tabela_notificacoes(conn)
        subs = conn.execute(
            text(
                """
            SELECT * FROM email_subscriptions
            WHERE provider IN ('outlook', 'outlook_calendar')
              AND (expires_at IS NULL OR expires_at <= NOW() + INTERVAL '12 hours')
        """
            )
        ).fetchall()
    for sub in subs:
        s = dict(sub._mapping)
        if not s.get("subscription_id"):
            continue
        new_exp = datetime.utcnow() + timedelta(minutes=4000)
        http_requests.patch(
            f"https://graph.microsoft.com/v1.0/subscriptions/{s['subscription_id']}",
            headers={
                "Authorization": f"Bearer {s.get('access_token', '')}",
                "Content-Type": "application/json",
            },
            json={"expirationDateTime": new_exp.strftime("%Y-%m-%dT%H:%M:%S.0000000Z")},
            timeout=10,
        )
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                UPDATE email_subscriptions SET expires_at=:exp, atualizado_em=NOW()
                WHERE subscription_id=:sid
            """
                ),
                {"exp": new_exp, "sid": s["subscription_id"]},
            )


# =========================
# SCHEDULER
# =========================
scheduler = BackgroundScheduler()
scheduler.add_job(verificar_rascunhos_expirados, "cron", hour=8, minute=0)
scheduler.add_job(renovar_gmail_watches, "interval", hours=6, id="renew_gmail")
scheduler.add_job(renovar_outlook_subscriptions, "interval", hours=6, id="renew_outlook")
scheduler.start()
print("⏰ Scheduler iniciado — verificação diária às 8h UTC")


# =========================
# ROTAS BÁSICAS
# =========================
@app.get("/")
def home():
    return {"msg": "API rodando 🚀"}


@app.post("/admin/verificar-rascunhos")
def trigger_verificar_rascunhos():
    verificar_rascunhos_expirados()
    return {"msg": "Verificação executada"}


# =========================
# NOTIFICAÇÕES
# =========================
@app.get("/notificacoes")
def listar_notificacoes(empresa_id: Optional[str] = None, email: str = Depends(get_current_user)):
    with engine.begin() as conn:
        garantir_tabela_notificacoes(conn)
        if empresa_id:
            result = conn.execute(
                text(
                    """
                SELECT * FROM notificacoes
                WHERE usuario_email = :email AND empresa_id = :eid
                ORDER BY criado_em DESC LIMIT 50
            """
                ),
                {"email": email, "eid": empresa_id},
            )
        else:
            result = conn.execute(
                text(
                    """
                SELECT * FROM notificacoes
                WHERE usuario_email = :email
                ORDER BY criado_em DESC LIMIT 50
            """
                ),
                {"email": email},
            )
        return [dict(row._mapping) for row in result]


@app.get("/notificacoes/nao-lidas")
def contar_nao_lidas(email: str = Depends(get_current_user)):
    with engine.begin() as conn:
        garantir_tabela_notificacoes(conn)
        result = conn.execute(
            text(
                """
            SELECT COUNT(*) as total FROM notificacoes
            WHERE usuario_email = :email AND lida = FALSE
        """
            ),
            {"email": email},
        ).fetchone()
        return {"total": result._mapping["total"]}


@app.put("/notificacoes/{notificacao_id}/ler")
def marcar_lida(notificacao_id: str, email: str = Depends(get_current_user)):
    with engine.begin() as conn:
        conn.execute(
            text(
                """
            UPDATE notificacoes SET lida = TRUE
            WHERE notificacao_id = :id AND usuario_email = :email
        """
            ),
            {"id": notificacao_id, "email": email},
        )
    return {"msg": "Notificação marcada como lida"}


@app.put("/notificacoes/ler-todas")
def marcar_todas_lidas(email: str = Depends(get_current_user)):
    with engine.begin() as conn:
        conn.execute(
            text(
                """
            UPDATE notificacoes SET lida = TRUE
            WHERE usuario_email = :email AND lida = FALSE
        """
            ),
            {"email": email},
        )
    return {"msg": "Todas as notificações marcadas como lidas"}


@app.delete("/notificacoes/{notificacao_id}")
def deletar_notificacao(notificacao_id: str, email: str = Depends(get_current_user)):
    with engine.begin() as conn:
        conn.execute(
            text(
                """
            DELETE FROM notificacoes
            WHERE notificacao_id = :id AND usuario_email = :email
        """
            ),
            {"id": notificacao_id, "email": email},
        )
    return {"msg": "Notificação removida"}


# =========================
# MEU PERFIL
# =========================
@app.get("/me")
def get_me(email: str = Depends(get_current_user)):
    with engine.connect() as conn:
        usuario = conn.execute(
            text(
                "SELECT usuario_id, nome, email, telefone, cargo, empresa_nome, bio, data_criacao FROM usuarios WHERE email = :email"
            ),
            {"email": email},
        ).fetchone()
    if not usuario:
        raise HTTPException(404, "Usuário não encontrado")
    return dict(usuario._mapping)


@app.put("/me")
def update_me(dados: UsuarioUpdate, email: str = Depends(get_current_user)):
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE usuarios SET
                    nome = COALESCE(:nome, nome),
                    telefone = COALESCE(:telefone, telefone),
                    cargo = COALESCE(:cargo, cargo),
                    empresa_nome = COALESCE(:empresa_nome, empresa_nome),
                    bio = COALESCE(:bio, bio)
                WHERE email = :email
            """
            ),
            {
                "nome": dados.nome,
                "telefone": dados.telefone,
                "cargo": dados.cargo,
                "empresa_nome": dados.empresa_nome,
                "bio": dados.bio,
                "email": email,
            },
        )
    return {"msg": "Perfil atualizado com sucesso 🚀"}


# =========================
# MICROSOFT OAUTH
# =========================
@app.get("/auth/outlook/login")
def outlook_login():
    url = (
        f"https://login.microsoftonline.com/{MICROSOFT_TENANT_ID}/oauth2/v2.0/authorize"
        f"?client_id={MICROSOFT_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={MICROSOFT_REDIRECT_URI}"
        f"&response_mode=query"
        f"&scope=openid%20profile%20email%20User.Read%20Mail.Read%20Mail.Send%20Calendars.ReadWrite%20offline_access"
    )
    return {"auth_url": url}


@app.get("/auth/outlook/callback")
async def outlook_callback(code: str, email: str = Depends(get_current_user)):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://login.microsoftonline.com/{MICROSOFT_TENANT_ID}/oauth2/v2.0/token",
            data={
                "client_id": MICROSOFT_CLIENT_ID,
                "client_secret": MICROSOFT_CLIENT_SECRET,
                "code": code,
                "redirect_uri": MICROSOFT_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
    tokens = response.json()
    if "access_token" not in tokens:
        raise HTTPException(400, f"Erro: {tokens.get('error_description', 'Erro desconhecido')}")
    with engine.begin() as conn:
        garantir_colunas_oauth(conn)
        conn.execute(
            text("UPDATE usuarios SET outlook_access_token = :a, outlook_refresh_token = :r WHERE email = :e"),
            {"a": tokens.get("access_token"), "r": tokens.get("refresh_token"), "e": email},
        )
    import threading

    threading.Thread(
        target=setup_outlook_subscription,
        args=(email, tokens.get("access_token"), tokens.get("refresh_token", "")),
        daemon=True,
    ).start()
    threading.Thread(
        target=setup_outlook_calendar_subscription,
        args=(email, tokens.get("access_token"), tokens.get("refresh_token", "")),
        daemon=True,
    ).start()
    return {"msg": "Outlook conectado com sucesso 🚀"}


@app.get("/auth/outlook/status")
def outlook_status(email: str = Depends(get_current_user)):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT outlook_access_token FROM usuarios WHERE email = :email"),
            {"email": email},
        ).fetchone()
    if not result:
        raise HTTPException(404, "Usuário não encontrado")
    return {"conectado": result._mapping.get("outlook_access_token") is not None}


@app.delete("/auth/outlook/disconnect")
def outlook_disconnect(email: str = Depends(get_current_user)):
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE usuarios SET outlook_access_token = NULL, outlook_refresh_token = NULL WHERE email = :email"),
            {"email": email},
        )
    return {"msg": "Outlook desconectado com sucesso"}


# =========================
# GOOGLE OAUTH
# =========================
@app.get("/auth/google/login")
def google_login():
    url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?client_id={GOOGLE_CLIENT_ID}"
        f"&response_type=code&redirect_uri={GOOGLE_REDIRECT_URI}"
        f"&scope=https://www.googleapis.com/auth/gmail.send%20"
        f"https://www.googleapis.com/auth/gmail.readonly%20"
        f"https://www.googleapis.com/auth/calendar.events%20"
        f"https://www.googleapis.com/auth/calendar"
        f"&access_type=offline&prompt=consent"
    )
    return {"auth_url": url}


@app.get("/auth/google/callback")
async def google_callback(code: str, email: str = Depends(get_current_user)):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
    tokens = response.json()
    if "access_token" not in tokens:
        raise HTTPException(400, f"Erro Google: {tokens.get('error_description', tokens)}")
    with engine.begin() as conn:
        garantir_colunas_oauth(conn)
        conn.execute(
            text("UPDATE usuarios SET google_access_token = :a, google_refresh_token = :r WHERE email = :e"),
            {"a": tokens.get("access_token"), "r": tokens.get("refresh_token"), "e": email},
        )
    async with httpx.AsyncClient() as client:
        userinfo_res = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {tokens.get('access_token')}"},
        )
    gmail_address = userinfo_res.json().get("email", email)
    import threading

    threading.Thread(
        target=setup_gmail_watch,
        args=(email, tokens.get("access_token"), tokens.get("refresh_token", ""), gmail_address),
        daemon=True,
    ).start()
    return {"msg": "Google conectado com sucesso 🚀"}


@app.get("/auth/google/status")
def google_status(email: str = Depends(get_current_user)):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT google_access_token FROM usuarios WHERE email = :email"),
            {"email": email},
        ).fetchone()
    if not result:
        raise HTTPException(404, "Usuário não encontrado")
    return {"conectado": result._mapping.get("google_access_token") is not None}


@app.delete("/auth/google/disconnect")
def google_disconnect(email: str = Depends(get_current_user)):
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE usuarios SET google_access_token = NULL, google_refresh_token = NULL WHERE email = :email"),
            {"email": email},
        )
    return {"msg": "Google desconectado com sucesso"}


# =========================
# TOKEN REFRESH HELPERS
# =========================
async def _refresh_outlook_token(refresh_token: str, email: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://login.microsoftonline.com/{MICROSOFT_TENANT_ID}/oauth2/v2.0/token",
            data={
                "client_id": MICROSOFT_CLIENT_ID,
                "client_secret": MICROSOFT_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": "openid profile email User.Read Mail.Read Mail.Send Calendars.ReadWrite offline_access",
            },
        )
    tokens = response.json()
    new_access = tokens.get("access_token")
    if new_access:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE usuarios SET outlook_access_token = :a, outlook_refresh_token = :r WHERE email = :e"),
                {"a": new_access, "r": tokens.get("refresh_token", refresh_token), "e": email},
            )
    return new_access


async def _refresh_google_token(refresh_token: str, email: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    tokens = response.json()
    new_access = tokens.get("access_token")
    if new_access:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE usuarios SET google_access_token = :a WHERE email = :e"),
                {"a": new_access, "e": email},
            )
    return new_access


# =========================
# REUNIÃO OUTLOOK
# =========================
@app.post("/eventos/{evento_id}/agendar-outlook")
async def agendar_reuniao_outlook(evento_id: str, reuniao: ReuniaoOutlook, email: str = Depends(get_current_user)):
    try:
        with engine.connect() as conn:
            usuario = conn.execute(
                text("SELECT outlook_access_token, outlook_refresh_token FROM usuarios WHERE email = :email"),
                {"email": email},
            ).fetchone()
        if not usuario or not usuario._mapping.get("outlook_access_token"):
            raise HTTPException(400, "Outlook não conectado.")
        access_token = usuario._mapping["outlook_access_token"]
        refresh_token = usuario._mapping.get("outlook_refresh_token")
        data_str = reuniao.data.isoformat()
        evento_graph = {
            "subject": reuniao.titulo,
            "body": {"contentType": "HTML", "content": reuniao.descricao or ""},
            "start": {"dateTime": f"{data_str}T{reuniao.hora_inicio}:00", "timeZone": "America/Sao_Paulo"},
            "end": {"dateTime": f"{data_str}T{reuniao.hora_fim}:00", "timeZone": "America/Sao_Paulo"},
        }
        if reuniao.email_convidado:
            evento_graph["attendees"] = [{"emailAddress": {"address": reuniao.email_convidado}, "type": "required"}]
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        async with httpx.AsyncClient() as client:
            response = await client.post("https://graph.microsoft.com/v1.0/me/events", json=evento_graph, headers=headers)
        if response.status_code == 401 and refresh_token:
            access_token = await _refresh_outlook_token(refresh_token, email)
            if not access_token:
                raise HTTPException(401, "Token expirado. Reconecte o Outlook.")
            headers["Authorization"] = f"Bearer {access_token}"
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://graph.microsoft.com/v1.0/me/events",
                    json=evento_graph,
                    headers=headers,
                )
        if response.status_code not in (200, 201):
            raise HTTPException(500, f"Erro Outlook: {response.text}")
        outlook_event = response.json()
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                UPDATE eventos SET outlook_event_id = :oid
                WHERE evento_id = :id AND usuario_email = :email
            """
                ),
                {"oid": outlook_event.get("id"), "id": evento_id, "email": email},
            )
        return {
            "msg": "Reunião criada no Outlook Calendar 🚀",
            "outlook_event_id": outlook_event.get("id"),
            "link": outlook_event.get("webLink"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# =========================
# REUNIÃO GOOGLE
# =========================
@app.post("/eventos/{evento_id}/agendar-google")
async def agendar_reuniao_google(evento_id: str, reuniao: ReuniaoGoogle, email: str = Depends(get_current_user)):
    try:
        with engine.connect() as conn:
            usuario = conn.execute(
                text("SELECT google_access_token, google_refresh_token FROM usuarios WHERE email = :email"),
                {"email": email},
            ).fetchone()
        if not usuario or not usuario._mapping.get("google_access_token"):
            raise HTTPException(400, "Google Calendar não conectado.")
        access_token = usuario._mapping["google_access_token"]
        refresh_token = usuario._mapping.get("google_refresh_token")
        data_str = reuniao.data.isoformat()
        evento_google = {
            "summary": reuniao.titulo,
            "description": reuniao.descricao or "",
            "start": {"dateTime": f"{data_str}T{reuniao.hora_inicio}:00", "timeZone": "America/Sao_Paulo"},
            "end": {"dateTime": f"{data_str}T{reuniao.hora_fim}:00", "timeZone": "America/Sao_Paulo"},
        }
        if reuniao.email_convidado:
            evento_google["attendees"] = [{"email": reuniao.email_convidado}]
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://www.googleapis.com/calendar/v3/calendars/primary/events?sendUpdates=all",
                json=evento_google,
                headers=headers,
            )
        if response.status_code == 401 and refresh_token:
            access_token = await _refresh_google_token(refresh_token, email)
            if not access_token:
                raise HTTPException(401, "Token expirado. Reconecte o Google.")
            headers["Authorization"] = f"Bearer {access_token}"
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://www.googleapis.com/calendar/v3/calendars/primary/events?sendUpdates=all",
                    json=evento_google,
                    headers=headers,
                )
        if response.status_code not in (200, 201):
            raise HTTPException(500, f"Erro Google Calendar: {response.text}")
        
        google_event = response.json()

        print("[GOOGLE EVENT]")
        print(json.dumps(google_event, indent=2))

        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                UPDATE eventos
                SET google_event_id = :gid
                WHERE evento_id = :id
                AND usuario_email = :email
            """
                ),
                {
                    "gid": google_event.get("id"),
                    "id": evento_id,
                    "email": email,
                },
            )


        return {
            "msg": "Reunião criada no Google Calendar 🚀",
            "google_event_id": google_event.get("id"),
            "link": google_event.get("htmlLink"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# =========================
# EVENTOS
# =========================
@app.get("/eventos")
def listar_eventos(email: str = Depends(get_current_user)):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM eventos WHERE usuario_email = :email ORDER BY data, hora_inicio"),
            {"email": email},
        )
        return [dict(row._mapping) for row in result]


@app.post("/eventos", status_code=201)
def criar_evento(evento: EventoCreate, email: str = Depends(get_current_user)):
    evento_id = str(uuid.uuid4())
    with engine.begin() as conn:
        garantir_tabela_notificacoes(conn)
        conn.execute(
            text(
                """
            INSERT INTO eventos (evento_id, titulo, tipo, data, hora_inicio, hora_fim,
                empresa_id, empresa_nome, descricao, usuario_email, criado_em)
            VALUES (:id, :titulo, :tipo, :data, :hora_inicio, :hora_fim,
                :empresa_id, :empresa_nome, :descricao, :email, NOW())
        """
            ),
            {
                "id": evento_id,
                "titulo": evento.titulo,
                "tipo": evento.tipo,
                "data": evento.data,
                "hora_inicio": evento.hora_inicio,
                "hora_fim": evento.hora_fim,
                "empresa_id": evento.empresa_id,
                "empresa_nome": evento.empresa_nome,
                "descricao": evento.descricao,
                "email": email,
            },
        )
    return {"msg": "Evento criado com sucesso 🚀", "id": evento_id}


@app.put("/eventos/{evento_id}")
def atualizar_evento(evento_id: str, evento: EventoUpdate, email: str = Depends(get_current_user)):
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT evento_id FROM eventos WHERE evento_id = :id AND usuario_email = :email"),
            {"id": evento_id, "email": email},
        ).fetchone()
        if not result:
            raise HTTPException(404, "Evento não encontrado")
        conn.execute(
            text(
                """
            UPDATE eventos SET titulo=COALESCE(:titulo,titulo), tipo=COALESCE(:tipo,tipo),
                data=COALESCE(:data,data), hora_inicio=COALESCE(:hora_inicio,hora_inicio),
                hora_fim=COALESCE(:hora_fim,hora_fim), empresa_id=COALESCE(:empresa_id,empresa_id),
                empresa_nome=COALESCE(:empresa_nome,empresa_nome), descricao=COALESCE(:descricao,descricao)
            WHERE evento_id=:id AND usuario_email=:email
        """
            ),
            {
                "titulo": evento.titulo,
                "tipo": evento.tipo,
                "data": evento.data,
                "hora_inicio": evento.hora_inicio,
                "hora_fim": evento.hora_fim,
                "empresa_id": evento.empresa_id,
                "empresa_nome": evento.empresa_nome,
                "descricao": evento.descricao,
                "id": evento_id,
                "email": email,
            },
        )
    return {"msg": "Evento atualizado com sucesso 🚀"}


@app.delete("/eventos/{evento_id}")
def deletar_evento(evento_id: str, email: str = Depends(get_current_user)):
    with engine.begin() as conn:
        result = conn.execute(
            text("DELETE FROM eventos WHERE evento_id=:id AND usuario_email=:email RETURNING evento_id"),
            {"id": evento_id, "email": email},
        ).fetchone()
    if not result:
        raise HTTPException(404, "Evento não encontrado")
    return {"msg": "Evento deletado com sucesso"}


# =========================
# SEGMENTOS
# =========================
@app.get("/segmentos")
def listar_segmentos():
    with engine.begin() as conn:
        garantir_tabela_segmentos(conn)
        result = conn.execute(text("SELECT nome FROM segmentos ORDER BY nome"))
        return {"segmentos": [row._mapping["nome"] for row in result]}


@app.post("/segmentos", status_code=201)
def criar_segmento(segmento: SegmentoCreate):
    with engine.begin() as conn:
        nome = salvar_segmento(conn, segmento.nome)
    return {"nome": nome, "validado": True}


# =========================
# EMPRESAS
# =========================
@app.get("/empresas")
def listar_empresas():
    with engine.begin() as conn:
        garantir_campos_pipeline(conn)
        result = conn.execute(
            text(
                """
            SELECT e.*, c.email AS contato_email, c.celular AS contato_celular, c.whatsapp AS contato_whatsapp
            FROM empresas e
            LEFT JOIN LATERAL (
                SELECT email, celular, whatsapp FROM contatos WHERE empresa_id = e.empresa_id
                ORDER BY decisor DESC NULLS LAST, data_criacao ASC NULLS LAST LIMIT 1
            ) c ON TRUE
            ORDER BY COALESCE(e.status_atualizado_em, e.ultima_interacao) DESC NULLS LAST, e.nome ASC
        """
            )
        )
        return [dict(row._mapping) for row in result]


@app.get("/empresas/{empresa_id}")
def buscar_empresa(empresa_id: str):
    with engine.begin() as conn:
        garantir_campos_pipeline(conn)
        result = conn.execute(
            text(
                """
            SELECT e.*, c.email AS contato_email, c.celular AS contato_celular, c.whatsapp AS contato_whatsapp
            FROM empresas e
            LEFT JOIN LATERAL (
                SELECT email, celular, whatsapp FROM contatos WHERE empresa_id = e.empresa_id
                ORDER BY decisor DESC NULLS LAST, data_criacao ASC NULLS LAST LIMIT 1
            ) c ON TRUE WHERE e.empresa_id = :id
        """
            ),
            {"id": empresa_id},
        ).fetchone()
    if not result:
        raise HTTPException(404, "Empresa não encontrada")
    return dict(result._mapping)


@app.get("/empresas/{empresa_id}/historico-status")
def historico_status_empresa(empresa_id: str):
    with engine.begin() as conn:
        garantir_campos_pipeline(conn)
        result = conn.execute(
            text("SELECT * FROM empresa_status_historico WHERE empresa_id = :id ORDER BY alterado_em DESC"),
            {"id": empresa_id},
        )
        return [dict(row._mapping) for row in result]


@app.get("/empresas/{empresa_id}/contatos")
def listar_contatos_por_empresa(empresa_id: str):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM contatos WHERE empresa_id = :id ORDER BY data_criacao ASC NULLS LAST"),
            {"id": empresa_id},
        )
        return [dict(row._mapping) for row in result]


@app.post("/empresas")
def criar_empresa(empresa: EmpresaCreate):
    empresa_id = str(uuid.uuid4())
    segmento = None
    is_rascunho = (empresa.status or "").lower() == "rascunho"
    if empresa.segmento and not is_rascunho:
        segmento = limpar_segmento(empresa.segmento)
        if not segmento_valido(segmento):
            raise HTTPException(400, "Segmento nao reconhecido.")
    elif empresa.segmento and is_rascunho:
        segmento = limpar_segmento(empresa.segmento) if empresa.segmento.strip() else None
    with engine.begin() as conn:
        garantir_campos_pipeline(conn)
        if segmento:
            segmento = salvar_segmento(conn, segmento)
        conn.execute(
            text(
                """
            INSERT INTO empresas (empresa_id, nome, segmento, porte, cidade, endereco, cep, bairro, regiao,
                observacoes, cnpj, site, linkedin_empresa, responsavel_principal, ticket_medio_estimado,
                status, origem_lead, ultima_interacao, proxima_acao, data_proxima_acao, status_atualizado_em,
                motivo_perdido, temperatura)
            VALUES (:id, :nome, :segmento, :porte, :cidade, :endereco, :cep, :bairro, :regiao,
                :observacoes, :cnpj, :site, :linkedin_empresa, :responsavel_principal, :ticket_medio_estimado,
                :status, :origem_lead, :ultima_interacao, :proxima_acao, :data_proxima_acao, NOW(),
                :motivo_perdido, :temperatura)
        """
            ),
            {
                "id": empresa_id,
                "nome": empresa.nome,
                "segmento": segmento,
                "porte": empresa.porte,
                "cidade": empresa.cidade,
                "endereco": empresa.endereco,
                "cep": empresa.cep,
                "bairro": empresa.bairro,
                "regiao": empresa.regiao,
                "observacoes": empresa.observacoes,
                "cnpj": empresa.cnpj,
                "site": empresa.site,
                "linkedin_empresa": empresa.linkedin_empresa,
                "responsavel_principal": empresa.responsavel_principal,
                "ticket_medio_estimado": empresa.ticket_medio_estimado,
                "status": empresa.status or "Lead",
                "origem_lead": empresa.origem_lead,
                "ultima_interacao": empresa.ultima_interacao or datetime.utcnow(),
                "proxima_acao": empresa.proxima_acao,
                "data_proxima_acao": empresa.data_proxima_acao,
                "motivo_perdido": empresa.motivo_perdido,
                "temperatura": empresa.temperatura,
            },
        )
        conn.execute(
            text(
                """
            INSERT INTO empresa_status_historico (historico_id, empresa_id, status_anterior, status_novo, observacao, alterado_em)
            VALUES (:id, :empresa_id, NULL, :status_novo, :observacao, NOW())
        """
            ),
            {
                "id": str(uuid.uuid4()),
                "empresa_id": empresa_id,
                "status_novo": empresa.status or "Lead",
                "observacao": "Rascunho salvo" if is_rascunho else "Cadastro inicial",
            },
        )
    return {"msg": "Empresa criada com sucesso 🚀", "empresa_id": empresa_id, "id": empresa_id}


@app.put("/empresas/{empresa_id}")
def atualizar_empresa(empresa_id: str, empresa: EmpresaUpdate):
    with engine.begin() as conn:
        garantir_campos_pipeline(conn)
        result = conn.execute(text("SELECT empresa_id, status FROM empresas WHERE empresa_id = :id"), {"id": empresa_id}).fetchone()
        if not result:
            raise HTTPException(404, "Empresa não encontrada")
        status_anterior = result._mapping.get("status")
        status_mudou = empresa.status is not None and empresa.status != status_anterior
        conn.execute(
            text(
                """
            UPDATE empresas SET nome=COALESCE(:nome,nome), segmento=COALESCE(:segmento,segmento),
                porte=COALESCE(:porte,porte), cidade=COALESCE(:cidade,cidade), endereco=COALESCE(:endereco,endereco),
                cep=COALESCE(:cep,cep), bairro=COALESCE(:bairro,bairro), regiao=COALESCE(:regiao,regiao),
                observacoes=COALESCE(:observacoes,observacoes), cnpj=COALESCE(:cnpj,cnpj), site=COALESCE(:site,site),
                linkedin_empresa=COALESCE(:linkedin_empresa,linkedin_empresa),
                responsavel_principal=COALESCE(:responsavel_principal,responsavel_principal),
                ticket_medio_estimado=COALESCE(:ticket_medio_estimado,ticket_medio_estimado),
                status=COALESCE(:status,status), origem_lead=COALESCE(:origem_lead,origem_lead),
                ultima_interacao=COALESCE(:ultima_interacao,ultima_interacao),
                proxima_acao=COALESCE(:proxima_acao,proxima_acao), data_proxima_acao=:data_proxima_acao,
                status_atualizado_em=CASE WHEN :status IS NOT NULL AND :status<>status THEN NOW() ELSE status_atualizado_em END,
                motivo_perdido=CASE WHEN :status IS NOT NULL AND :status<>'Perdido' THEN NULL ELSE COALESCE(:motivo_perdido,motivo_perdido) END,
                temperatura=COALESCE(:temperatura,temperatura)
            WHERE empresa_id=:id
        """
            ),
            {
                "id": empresa_id,
                "nome": empresa.nome,
                "segmento": empresa.segmento,
                "porte": empresa.porte,
                "cidade": empresa.cidade,
                "endereco": empresa.endereco,
                "cep": empresa.cep,
                "bairro": empresa.bairro,
                "regiao": empresa.regiao,
                "observacoes": empresa.observacoes,
                "cnpj": empresa.cnpj,
                "site": empresa.site,
                "linkedin_empresa": empresa.linkedin_empresa,
                "responsavel_principal": empresa.responsavel_principal,
                "ticket_medio_estimado": empresa.ticket_medio_estimado,
                "status": empresa.status,
                "origem_lead": empresa.origem_lead,
                "ultima_interacao": empresa.ultima_interacao,
                "proxima_acao": empresa.proxima_acao,
                "data_proxima_acao": empresa.data_proxima_acao,
                "motivo_perdido": empresa.motivo_perdido,
                "temperatura": empresa.temperatura,
            },
        )
        if status_mudou:
            conn.execute(
                text(
                    """
                INSERT INTO empresa_status_historico (historico_id, empresa_id, status_anterior, status_novo, observacao, alterado_em)
                VALUES (:id, :empresa_id, :status_anterior, :status_novo, :observacao, NOW())
            """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "empresa_id": empresa_id,
                    "status_anterior": status_anterior,
                    "status_novo": empresa.status,
                    "observacao": empresa.motivo_perdido if empresa.status == "Perdido" else None,
                },
            )
    return {"msg": "Empresa atualizada com sucesso 🚀"}


@app.delete("/empresas/{empresa_id}")
def deletar_empresa(empresa_id: str):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM contatos WHERE empresa_id = :id"), {"id": empresa_id})
        conn.execute(text("DELETE FROM empresa_status_historico WHERE empresa_id = :id"), {"id": empresa_id})
        result = conn.execute(text("DELETE FROM empresas WHERE empresa_id = :id RETURNING empresa_id"), {"id": empresa_id}).fetchone()
    if not result:
        raise HTTPException(404, "Empresa não encontrada")
    return {"msg": "Empresa deletada com sucesso"}


# =========================
# CONTATOS
# =========================
@app.get("/contatos/{empresa_id}")
def listar_contatos_empresa(empresa_id: str):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM contatos WHERE empresa_id = :id ORDER BY data_criacao ASC NULLS LAST"),
            {"id": empresa_id},
        )
        return [dict(row._mapping) for row in result]


@app.post("/contatos")
def criar_contato(contato: dict):
    with engine.begin() as conn:
        conn.execute(
            text(
                """
            INSERT INTO contatos (contato_id, empresa_id, nome, funcao, email, celular, observacoes,
                prioridade, whatsapp, linkedin, nivel_influencia, decisor, data_ultimo_contato, canal_preferido)
            VALUES (:id, :empresa_id, :nome, :funcao, :email, :celular, :observacoes,
                :prioridade, :whatsapp, :linkedin, :nivel_influencia, :decisor, :data_ultimo_contato, :canal_preferido)
        """
            ),
            {
                "id": str(uuid.uuid4()),
                "empresa_id": contato.get("empresa_id"),
                "nome": contato.get("nome"),
                "funcao": contato.get("funcao"),
                "email": contato.get("email"),
                "celular": contato.get("celular"),
                "observacoes": contato.get("observacoes"),
                "prioridade": contato.get("prioridade"),
                "whatsapp": contato.get("whatsapp"),
                "linkedin": contato.get("linkedin"),
                "nivel_influencia": contato.get("nivel_influencia"),
                "decisor": contato.get("decisor"),
                "data_ultimo_contato": contato.get("data_ultimo_contato"),
                "canal_preferido": contato.get("canal_preferido"),
            },
        )
    return {"msg": "Contato criado com sucesso 🚀"}


@app.put("/contatos/{contato_id}")
def atualizar_contato(contato_id: str, contato: ContatoUpdate):
    with engine.begin() as conn:
        result = conn.execute(text("SELECT contato_id FROM contatos WHERE contato_id = :id"), {"id": contato_id}).fetchone()
        if not result:
            raise HTTPException(404, "Contato não encontrado")
        conn.execute(
            text(
                """
            UPDATE contatos SET nome=COALESCE(:nome,nome), funcao=COALESCE(:funcao,funcao),
                email=COALESCE(:email,email), celular=COALESCE(:celular,celular),
                whatsapp=COALESCE(:whatsapp,whatsapp), linkedin=COALESCE(:linkedin,linkedin),
                observacoes=COALESCE(:observacoes,observacoes), prioridade=COALESCE(:prioridade,prioridade),
                nivel_influencia=COALESCE(:nivel_influencia,nivel_influencia), decisor=COALESCE(:decisor,decisor),
                canal_preferido=COALESCE(:canal_preferido,canal_preferido),
                data_ultimo_contato=COALESCE(:data_ultimo_contato,data_ultimo_contato)
            WHERE contato_id=:id
        """
            ),
            {
                "id": contato_id,
                "nome": contato.nome,
                "funcao": contato.funcao,
                "email": contato.email,
                "celular": contato.celular,
                "whatsapp": contato.whatsapp,
                "linkedin": contato.linkedin,
                "observacoes": contato.observacoes,
                "prioridade": contato.prioridade,
                "nivel_influencia": contato.nivel_influencia,
                "decisor": contato.decisor,
                "canal_preferido": contato.canal_preferido,
                "data_ultimo_contato": contato.data_ultimo_contato,
            },
        )
    return {"msg": "Contato atualizado com sucesso 🚀"}


@app.delete("/contatos/{contato_id}")
def deletar_contato(contato_id: str):
    with engine.begin() as conn:
        result = conn.execute(text("DELETE FROM contatos WHERE contato_id = :id RETURNING contato_id"), {"id": contato_id}).fetchone()
    if not result:
        raise HTTPException(404, "Contato não encontrado")
    return {"msg": "Contato deletado com sucesso"}


# =========================
# USUÁRIOS
# =========================
@app.post("/usuarios", status_code=201)
async def criar_usuario(usuario: UsuarioCreate):
    token_ativacao = str(uuid.uuid4())
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                INSERT INTO usuarios (usuario_id, nome, email, telefone, ativo, token_ativacao, data_criacao)
                VALUES (:usuario_id, :nome, :email, :telefone, FALSE, :token, NOW())
            """
                ),
                {
                    "usuario_id": str(uuid.uuid4()),
                    "nome": usuario.nome,
                    "email": usuario.email,
                    "telefone": usuario.telefone,
                    "token": token_ativacao,
                },
            )
        await enviar_email(usuario.email, token_ativacao)
        return {"msg": "Usuário criado. Verifique seu email 📩"}
    except IntegrityError:
        raise HTTPException(400, "Email já cadastrado")


@app.post("/ativar-conta")
def ativar_conta(dados: AtivarConta):
    senha_hash = hash_senha(dados.senha)
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
            UPDATE usuarios SET senha_hash = :senha, ativo = TRUE, token_ativacao = NULL
            WHERE token_ativacao = :token RETURNING usuario_id
        """
            ),
            {"senha": senha_hash, "token": dados.token},
        ).fetchone()
        if not result:
            raise HTTPException(400, "Token inválido")
    return {"msg": "Conta ativada com sucesso 🚀"}


@app.post("/login", response_model=Token)
def login(dados: Login):
    with engine.connect() as conn:
        usuario = conn.execute(text("SELECT * FROM usuarios WHERE email = :email"), {"email": dados.email}).fetchone()
    if not usuario:
        raise HTTPException(401, "Usuário não encontrado")
    usuario = dict(usuario._mapping)
    if not usuario["ativo"]:
        raise HTTPException(401, "Conta não ativada")
    if not verificar_senha(dados.senha, usuario["senha_hash"]):
        raise HTTPException(401, "Senha inválida")
    token = criar_token_acesso({"sub": usuario["email"]})
    return {"access_token": token, "token_type": "bearer"}
