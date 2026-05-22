# =========================
# IMPORTAÇÕES
# =========================
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext
from datetime import datetime, timedelta, date, time
from typing import Optional
import uuid
import jwt
import os
import re
import unicodedata
import httpx
import resend

print("🔥 ENV DATABASE_URL:", os.getenv("DATABASE_URL"))

# =========================
# CONFIG
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("🚨 DATABASE_URL não encontrada!")

SECRET_KEY = "super_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 horas

resend.api_key = os.getenv("RESEND_API_KEY")

# Microsoft OAuth
MICROSOFT_CLIENT_ID     = os.getenv("MICROSOFT_CLIENT_ID")
MICROSOFT_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET")
MICROSOFT_TENANT_ID     = os.getenv("MICROSOFT_TENANT_ID")
MICROSOFT_REDIRECT_URI  = os.getenv("MICROSOFT_REDIRECT_URI")

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
    "Academias e Fitness", "Administracao de Condominios", "Advocacia",
    "Agencia de Marketing", "Agencia de Publicidade", "Agronegocio",
    "Alimentos e Bebidas", "Arquitetura e Urbanismo", "Assistencia Tecnica",
    "Atacado e Distribuicao", "Automacao Industrial", "Autopecas",
    "Bares e Restaurantes", "Beleza e Estetica", "Biotecnologia",
    "Clinicas Medicas", "Comercio Exterior", "Comercio Varejista",
    "Concessionarias", "Construcao Civil", "Consultoria Empresarial",
    "Contabilidade", "Coworking", "Cursos e Treinamentos", "Decoracao",
    "Distribuidora", "E-commerce", "Educacao", "Energia", "Energia Solar",
    "Engenharia", "Entretenimento", "Escritorio de Projetos", "Eventos",
    "Farmacias e Drogarias", "Financeiro", "Franquias", "Gestao de Pessoas",
    "Hotelaria", "Imobiliarias", "Industria Alimenticia", "Industria Automotiva",
    "Industria Farmaceutica", "Industria Metalurgica", "Industria Textil",
    "Logistica e Transporte", "Manutencao Predial", "Maquinas e Equipamentos",
    "Materiais de Construcao", "Moda e Vestuario", "Moveis Planejados",
    "Odontologia", "Pet Shop", "Produtos Agropecuarios", "Recursos Humanos",
    "Saude", "Seguranca Eletronica", "Seguros", "Servicos de Limpeza",
    "Servicos Financeiros", "Software e SaaS", "Supermercados",
    "Tecnologia da Informacao", "Telecomunicacoes", "Turismo", "Venda de Gado",
    "Vendas B2B", "Veterinaria", "Agropecuaria", "Clinicas Odontologicas",
    "Confeitaria", "Delivery", "Grafica", "Hospitais", "Jardinagem e Paisagismo",
    "Laboratorios", "Laticinios", "Lavanderias", "Marcenaria", "Padarias",
    "Papelarias", "Postos de Combustivel", "Serralheria", "Transportadoras",
]

PALAVRAS_CHAVE_SEGMENTO = {
    "academia", "administracao", "advocacia", "agencia", "agro", "agronegocio",
    "alimento", "arquitetura", "assistencia", "atacado", "automacao", "autopecas",
    "bar", "beleza", "biotecnologia", "clinica", "comercio", "condominio",
    "concessionaria", "construcao", "consultoria", "contabilidade", "coworking",
    "curso", "decoracao", "distribuicao", "distribuidora", "ecommerce", "educacao",
    "energia", "engenharia", "entretenimento", "escola", "evento", "farmacia",
    "financeiro", "fitness", "franquia", "gado", "gestao", "hotel", "imobiliaria",
    "industria", "limpeza", "logistica", "manutencao", "maquinas", "marketing",
    "materiais", "medica", "metalurgica", "moda", "moveis", "odontologia",
    "oficina", "papelaria", "pet", "projetos", "publicidade", "recursos",
    "restaurante", "rh", "saas", "saude", "seguranca", "seguros", "servicos",
    "software", "solar", "supermercado", "tecnologia", "telecomunicacoes",
    "textil", "transporte", "turismo", "varejo", "vendas", "veterinaria",
    "agropecuaria", "combustivel", "confeitaria", "contabil", "delivery",
    "frigorifico", "grafica", "hospital", "jardinagem", "juridico",
    "laboratorio", "laticinios", "lavanderia", "marcenaria", "padaria",
    "paisagismo", "panificadora", "pecuaria", "posto", "rural",
    "serralheria", "transportadora",
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
    resend.Emails.send({
        "from": "onboarding@resend.dev",
        "to": destino,
        "subject": "Ative sua conta 🚀",
        "html": f"<p>Olá!</p><p>Clique no link abaixo para criar sua senha:</p><p><a href='{link}'>{link}</a></p>"
    })

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
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS segmentos (
            segmento_id uuid PRIMARY KEY,
            nome character varying(120) NOT NULL,
            nome_normalizado character varying(120) UNIQUE NOT NULL,
            criado_em timestamp without time zone DEFAULT CURRENT_TIMESTAMP
        )
    """))
    for segmento in SEGMENTOS_PADRAO:
        nome = limpar_segmento(segmento)
        conn.execute(
            text("""
                INSERT INTO segmentos (segmento_id, nome, nome_normalizado)
                VALUES (:id, :nome, :nome_normalizado)
                ON CONFLICT (nome_normalizado) DO NOTHING
            """),
            {"id": str(uuid.uuid4()), "nome": nome, "nome_normalizado": normalizar_texto(nome)}
        )

def salvar_segmento(conn, nome: str) -> str:
    nome_limpo = limpar_segmento(nome)
    if not segmento_valido(nome_limpo):
        raise HTTPException(
            400,
            "Segmento nao reconhecido. Escolha um segmento da lista ou informe um segmento de mercado valido."
        )
    garantir_tabela_segmentos(conn)
    conn.execute(
        text("""
            INSERT INTO segmentos (segmento_id, nome, nome_normalizado)
            VALUES (:id, :nome, :nome_normalizado)
            ON CONFLICT (nome_normalizado) DO UPDATE SET nome = EXCLUDED.nome
        """),
        {"id": str(uuid.uuid4()), "nome": nome_limpo, "nome_normalizado": normalizar_texto(nome_limpo)}
    )
    return nome_limpo

def garantir_campos_pipeline(conn):
    conn.execute(text("ALTER TABLE empresas ADD COLUMN IF NOT EXISTS data_proxima_acao date"))
    conn.execute(text("ALTER TABLE empresas ADD COLUMN IF NOT EXISTS status_atualizado_em timestamp without time zone DEFAULT CURRENT_TIMESTAMP"))
    conn.execute(text("ALTER TABLE empresas ADD COLUMN IF NOT EXISTS motivo_perdido text"))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS empresa_status_historico (
            historico_id uuid PRIMARY KEY,
            empresa_id uuid NOT NULL,
            status_anterior character varying(50),
            status_novo character varying(50) NOT NULL,
            observacao text,
            alterado_em timestamp without time zone DEFAULT CURRENT_TIMESTAMP
        )
    """))

def garantir_colunas_outlook(conn):
    conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS outlook_access_token text"))
    conn.execute(text("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS outlook_refresh_token text"))

# =========================
# ROTAS BÁSICAS
# =========================
@app.get("/")
def home():
    return {"msg": "API rodando 🚀"}

# =========================
# MEU PERFIL
# =========================
@app.get("/me")
def get_me(email: str = Depends(get_current_user)):
    with engine.connect() as conn:
        usuario = conn.execute(
            text("SELECT usuario_id, nome, email, telefone, cargo, empresa_nome, bio, data_criacao FROM usuarios WHERE email = :email"),
            {"email": email}
        ).fetchone()
    if not usuario:
        raise HTTPException(404, "Usuário não encontrado")
    return dict(usuario._mapping)

@app.put("/me")
def update_me(dados: UsuarioUpdate, email: str = Depends(get_current_user)):
    with engine.begin() as conn:
        conn.execute(
            text("""
                UPDATE usuarios SET
                    nome = COALESCE(:nome, nome),
                    telefone = COALESCE(:telefone, telefone),
                    cargo = COALESCE(:cargo, cargo),
                    empresa_nome = COALESCE(:empresa_nome, empresa_nome),
                    bio = COALESCE(:bio, bio)
                WHERE email = :email
            """),
            {"nome": dados.nome, "telefone": dados.telefone, "cargo": dados.cargo,
             "empresa_nome": dados.empresa_nome, "bio": dados.bio, "email": email}
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
        f"&scope=Calendars.ReadWrite%20Mail.Send%20offline_access"
        f"&response_mode=query"
    )
    return {"auth_url": url}

@app.get("/auth/outlook/callback")
async def outlook_callback(code: str, email: str = Depends(get_current_user)):
    print(f"📩 OUTLOOK CALLBACK recebido para: {email}")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://login.microsoftonline.com/{MICROSOFT_TENANT_ID}/oauth2/v2.0/token",
            data={
                "client_id": MICROSOFT_CLIENT_ID,
                "client_secret": MICROSOFT_CLIENT_SECRET,
                "code": code,
                "redirect_uri": MICROSOFT_REDIRECT_URI,
                "grant_type": "authorization_code",
            }
        )
    tokens = response.json()
    print(f"📩 OUTLOOK TOKEN RESPONSE status: {response.status_code}")
    if "access_token" not in tokens:
        raise HTTPException(400, f"Erro ao obter tokens: {tokens.get('error_description', 'Erro desconhecido')}")

    with engine.begin() as conn:
        garantir_colunas_outlook(conn)
        conn.execute(text("""
            UPDATE usuarios SET
                outlook_access_token = :access,
                outlook_refresh_token = :refresh
            WHERE email = :email
        """), {
            "access": tokens.get("access_token"),
            "refresh": tokens.get("refresh_token"),
            "email": email
        })
    print(f"✅ OUTLOOK tokens salvos para: {email}")
    return {"msg": "Outlook conectado com sucesso 🚀"}

@app.get("/auth/outlook/status")
def outlook_status(email: str = Depends(get_current_user)):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT outlook_access_token FROM usuarios WHERE email = :email"),
            {"email": email}
        ).fetchone()
    if not result:
        raise HTTPException(404, "Usuário não encontrado")
    conectado = result._mapping.get("outlook_access_token") is not None
    return {"conectado": conectado}

@app.delete("/auth/outlook/disconnect")
def outlook_disconnect(email: str = Depends(get_current_user)):
    with engine.begin() as conn:
        conn.execute(text("""
            UPDATE usuarios SET
                outlook_access_token = NULL,
                outlook_refresh_token = NULL
            WHERE email = :email
        """), {"email": email})
    return {"msg": "Outlook desconectado com sucesso"}

# =========================
# REUNIÃO OUTLOOK CALENDAR
# =========================
async def _refresh_outlook_token(refresh_token: str, email: str) -> str:
    """Renova o access_token usando o refresh_token e salva no banco."""
    print(f"🔄 Tentando refresh do token para: {email}")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://login.microsoftonline.com/{MICROSOFT_TENANT_ID}/oauth2/v2.0/token",
            data={
                "client_id": MICROSOFT_CLIENT_ID,
                "client_secret": MICROSOFT_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": "Calendars.ReadWrite Mail.Send offline_access",
            }
        )
    tokens = response.json()
    new_access = tokens.get("access_token")
    new_refresh = tokens.get("refresh_token", refresh_token)
    print(f"🔄 Refresh response status: {response.status_code} | novo token obtido: {bool(new_access)}")

    if new_access:
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE usuarios SET
                    outlook_access_token = :access,
                    outlook_refresh_token = :refresh
                WHERE email = :email
            """), {"access": new_access, "refresh": new_refresh, "email": email})
        print(f"✅ Novo token salvo para: {email}")
    else:
        print(f"🔴 Falha no refresh: {tokens}")

    return new_access

@app.post("/eventos/{evento_id}/agendar-outlook")
async def agendar_reuniao_outlook(evento_id: str, reuniao: ReuniaoOutlook, email: str = Depends(get_current_user)):
    """Cria uma reunião no Outlook Calendar do usuário e envia convite ao cliente."""
    try:
        print(f"📅 Iniciando agendamento Outlook para evento {evento_id} | usuário: {email}")

        with engine.connect() as conn:
            usuario = conn.execute(
                text("SELECT outlook_access_token, outlook_refresh_token FROM usuarios WHERE email = :email"),
                {"email": email}
            ).fetchone()

        if not usuario or not usuario._mapping.get("outlook_access_token"):
            raise HTTPException(400, "Outlook não conectado. Acesse /auth/outlook/login primeiro.")

        access_token = usuario._mapping["outlook_access_token"]
        refresh_token = usuario._mapping.get("outlook_refresh_token")
        print(f"📅 Token encontrado. Refresh disponível: {bool(refresh_token)}")

        data_str = reuniao.data.isoformat()
        evento_graph = {
            "subject": reuniao.titulo,
            "body": {"contentType": "HTML", "content": reuniao.descricao or ""},
            "start": {"dateTime": f"{data_str}T{reuniao.hora_inicio}:00", "timeZone": "America/Sao_Paulo"},
            "end":   {"dateTime": f"{data_str}T{reuniao.hora_fim}:00",   "timeZone": "America/Sao_Paulo"},
        }
        if reuniao.email_convidado:
            evento_graph["attendees"] = [{
                "emailAddress": {"address": reuniao.email_convidado},
                "type": "required"
            }]

        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://graph.microsoft.com/v1.0/me/events",
                json=evento_graph,
                headers=headers
            )

        print(f"📬 OUTLOOK RESPONSE: {response.status_code} - {response.text[:300]}")

        # Se token expirou, renova e tenta de novo
        if response.status_code == 401 and refresh_token:
            print(f"🔄 Token expirado, tentando renovar...")
            access_token = await _refresh_outlook_token(refresh_token, email)
            if not access_token:
                raise HTTPException(401, "Token expirado e não foi possível renovar. Reconecte o Outlook.")
            headers["Authorization"] = f"Bearer {access_token}"
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://graph.microsoft.com/v1.0/me/events",
                    json=evento_graph,
                    headers=headers
                )
            print(f"📬 OUTLOOK RESPONSE (após refresh): {response.status_code} - {response.text[:300]}")

        if response.status_code not in (200, 201):
            print(f"🔴 OUTLOOK ERROR FINAL: {response.status_code} - {response.text}")
            raise HTTPException(500, f"Erro ao criar evento no Outlook: {response.text}")

        outlook_event = response.json()
        print(f"✅ Evento criado no Outlook: {outlook_event.get('id')}")
        print(f"📧 Convidado enviado para: {reuniao.email_convidado}")
        print(f"📧 Attendees no evento: {evento_graph.get('attendees')}")
        return {
            "msg": "Reunião criada no Outlook Calendar 🚀",
            "outlook_event_id": outlook_event.get("id"),
            "link": outlook_event.get("webLink")
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"🔴 EXCEPTION agendar-outlook: {str(e)}")
        raise HTTPException(500, str(e))

# =========================
# EVENTOS
# =========================
@app.get("/eventos")
def listar_eventos(email: str = Depends(get_current_user)):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM eventos WHERE usuario_email = :email ORDER BY data, hora_inicio"),
            {"email": email}
        )
        return [dict(row._mapping) for row in result]

@app.post("/eventos", status_code=201)
def criar_evento(evento: EventoCreate, email: str = Depends(get_current_user)):
    evento_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO eventos (
                    evento_id, titulo, tipo, data, hora_inicio, hora_fim,
                    empresa_id, empresa_nome, descricao, usuario_email, criado_em
                ) VALUES (
                    :id, :titulo, :tipo, :data, :hora_inicio, :hora_fim,
                    :empresa_id, :empresa_nome, :descricao, :email, NOW()
                )
            """),
            {
                "id": evento_id, "titulo": evento.titulo, "tipo": evento.tipo,
                "data": evento.data, "hora_inicio": evento.hora_inicio, "hora_fim": evento.hora_fim,
                "empresa_id": evento.empresa_id, "empresa_nome": evento.empresa_nome,
                "descricao": evento.descricao, "email": email,
            }
        )
    return {"msg": "Evento criado com sucesso 🚀", "id": evento_id}

@app.put("/eventos/{evento_id}")
def atualizar_evento(evento_id: str, evento: EventoUpdate, email: str = Depends(get_current_user)):
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT evento_id FROM eventos WHERE evento_id = :id AND usuario_email = :email"),
            {"id": evento_id, "email": email}
        ).fetchone()
        if not result:
            raise HTTPException(404, "Evento não encontrado")
        conn.execute(
            text("""
                UPDATE eventos SET
                    titulo = COALESCE(:titulo, titulo), tipo = COALESCE(:tipo, tipo),
                    data = COALESCE(:data, data), hora_inicio = COALESCE(:hora_inicio, hora_inicio),
                    hora_fim = COALESCE(:hora_fim, hora_fim), empresa_id = COALESCE(:empresa_id, empresa_id),
                    empresa_nome = COALESCE(:empresa_nome, empresa_nome), descricao = COALESCE(:descricao, descricao)
                WHERE evento_id = :id AND usuario_email = :email
            """),
            {
                "titulo": evento.titulo, "tipo": evento.tipo, "data": evento.data,
                "hora_inicio": evento.hora_inicio, "hora_fim": evento.hora_fim,
                "empresa_id": evento.empresa_id, "empresa_nome": evento.empresa_nome,
                "descricao": evento.descricao, "id": evento_id, "email": email
            }
        )
    return {"msg": "Evento atualizado com sucesso 🚀"}

@app.delete("/eventos/{evento_id}")
def deletar_evento(evento_id: str, email: str = Depends(get_current_user)):
    with engine.begin() as conn:
        result = conn.execute(
            text("DELETE FROM eventos WHERE evento_id = :id AND usuario_email = :email RETURNING evento_id"),
            {"id": evento_id, "email": email}
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
        result = conn.execute(text("""
            SELECT e.*, c.email AS contato_email, c.celular AS contato_celular, c.whatsapp AS contato_whatsapp
            FROM empresas e
            LEFT JOIN LATERAL (
                SELECT email, celular, whatsapp
                FROM contatos
                WHERE empresa_id = e.empresa_id
                ORDER BY decisor DESC NULLS LAST, data_criacao ASC NULLS LAST
                LIMIT 1
            ) c ON TRUE
            ORDER BY COALESCE(e.status_atualizado_em, e.ultima_interacao) DESC NULLS LAST, e.nome ASC
        """))
        return [dict(row._mapping) for row in result]

@app.get("/empresas/{empresa_id}")
def buscar_empresa(empresa_id: str):
    with engine.begin() as conn:
        garantir_campos_pipeline(conn)
        result = conn.execute(
            text("""
                SELECT e.*, c.email AS contato_email, c.celular AS contato_celular, c.whatsapp AS contato_whatsapp
                FROM empresas e
                LEFT JOIN LATERAL (
                    SELECT email, celular, whatsapp
                    FROM contatos
                    WHERE empresa_id = e.empresa_id
                    ORDER BY decisor DESC NULLS LAST, data_criacao ASC NULLS LAST
                    LIMIT 1
                ) c ON TRUE
                WHERE e.empresa_id = :id
            """), {"id": empresa_id}
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
            {"id": empresa_id}
        )
        return [dict(row._mapping) for row in result]

@app.get("/empresas/{empresa_id}/contatos")
def listar_contatos_por_empresa(empresa_id: str):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM contatos WHERE empresa_id = :id ORDER BY data_criacao ASC NULLS LAST"),
            {"id": empresa_id}
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
            raise HTTPException(400, "Segmento nao reconhecido. Escolha um segmento da lista ou informe um segmento de mercado valido.")
    elif empresa.segmento and is_rascunho:
        segmento = limpar_segmento(empresa.segmento) if empresa.segmento.strip() else None

    with engine.begin() as conn:
        garantir_campos_pipeline(conn)
        if segmento:
            segmento = salvar_segmento(conn, segmento)
        conn.execute(
            text("""
                INSERT INTO empresas (
                    empresa_id, nome, segmento, porte, cidade, endereco, cep, bairro, regiao,
                    observacoes, cnpj, site, linkedin_empresa, responsavel_principal,
                    ticket_medio_estimado, status, origem_lead, ultima_interacao, proxima_acao,
                    data_proxima_acao, status_atualizado_em, motivo_perdido, temperatura
                ) VALUES (
                    :id, :nome, :segmento, :porte, :cidade, :endereco, :cep, :bairro, :regiao,
                    :observacoes, :cnpj, :site, :linkedin_empresa, :responsavel_principal,
                    :ticket_medio_estimado, :status, :origem_lead, :ultima_interacao, :proxima_acao,
                    :data_proxima_acao, NOW(), :motivo_perdido, :temperatura
                )
            """),
            {
                "id": empresa_id, "nome": empresa.nome, "segmento": segmento,
                "porte": empresa.porte, "cidade": empresa.cidade, "endereco": empresa.endereco,
                "cep": empresa.cep, "bairro": empresa.bairro, "regiao": empresa.regiao,
                "observacoes": empresa.observacoes, "cnpj": empresa.cnpj, "site": empresa.site,
                "linkedin_empresa": empresa.linkedin_empresa,
                "responsavel_principal": empresa.responsavel_principal,
                "ticket_medio_estimado": empresa.ticket_medio_estimado,
                "status": empresa.status or "Lead",
                "origem_lead": empresa.origem_lead,
                "ultima_interacao": empresa.ultima_interacao or datetime.utcnow(),
                "proxima_acao": empresa.proxima_acao,
                "data_proxima_acao": empresa.data_proxima_acao,
                "motivo_perdido": empresa.motivo_perdido,
                "temperatura": empresa.temperatura
            }
        )
        status_inicial = empresa.status or "Lead"
        conn.execute(
            text("""
                INSERT INTO empresa_status_historico (
                    historico_id, empresa_id, status_anterior, status_novo, observacao, alterado_em
                ) VALUES (:id, :empresa_id, NULL, :status_novo, :observacao, NOW())
            """),
            {
                "id": str(uuid.uuid4()), "empresa_id": empresa_id,
                "status_novo": status_inicial,
                "observacao": "Rascunho salvo" if is_rascunho else "Cadastro inicial"
            }
        )
    return {"msg": "Empresa criada com sucesso 🚀", "empresa_id": empresa_id, "id": empresa_id}

@app.put("/empresas/{empresa_id}")
def atualizar_empresa(empresa_id: str, empresa: EmpresaUpdate):
    with engine.begin() as conn:
        garantir_campos_pipeline(conn)
        result = conn.execute(
            text("SELECT empresa_id, status FROM empresas WHERE empresa_id = :id"), {"id": empresa_id}
        ).fetchone()
        if not result:
            raise HTTPException(404, "Empresa não encontrada")

        status_anterior = result._mapping.get("status")
        status_mudou = empresa.status is not None and empresa.status != status_anterior

        conn.execute(
            text("""
                UPDATE empresas SET
                    nome = COALESCE(:nome, nome),
                    segmento = COALESCE(:segmento, segmento),
                    porte = COALESCE(:porte, porte),
                    cidade = COALESCE(:cidade, cidade),
                    endereco = COALESCE(:endereco, endereco),
                    cep = COALESCE(:cep, cep),
                    bairro = COALESCE(:bairro, bairro),
                    regiao = COALESCE(:regiao, regiao),
                    observacoes = COALESCE(:observacoes, observacoes),
                    cnpj = COALESCE(:cnpj, cnpj),
                    site = COALESCE(:site, site),
                    linkedin_empresa = COALESCE(:linkedin_empresa, linkedin_empresa),
                    responsavel_principal = COALESCE(:responsavel_principal, responsavel_principal),
                    ticket_medio_estimado = COALESCE(:ticket_medio_estimado, ticket_medio_estimado),
                    status = COALESCE(:status, status),
                    origem_lead = COALESCE(:origem_lead, origem_lead),
                    ultima_interacao = COALESCE(:ultima_interacao, ultima_interacao),
                    proxima_acao = COALESCE(:proxima_acao, proxima_acao),
                    data_proxima_acao = :data_proxima_acao,
                    status_atualizado_em = CASE
                        WHEN :status IS NOT NULL AND :status <> status THEN NOW()
                        ELSE status_atualizado_em
                    END,
                    motivo_perdido = CASE
                        WHEN :status IS NOT NULL AND :status <> 'Perdido' THEN NULL
                        ELSE COALESCE(:motivo_perdido, motivo_perdido)
                    END,
                    temperatura = COALESCE(:temperatura, temperatura)
                WHERE empresa_id = :id
            """),
            {
                "id": empresa_id, "nome": empresa.nome, "segmento": empresa.segmento,
                "porte": empresa.porte, "cidade": empresa.cidade, "endereco": empresa.endereco,
                "cep": empresa.cep, "bairro": empresa.bairro, "regiao": empresa.regiao,
                "observacoes": empresa.observacoes, "cnpj": empresa.cnpj, "site": empresa.site,
                "linkedin_empresa": empresa.linkedin_empresa,
                "responsavel_principal": empresa.responsavel_principal,
                "ticket_medio_estimado": empresa.ticket_medio_estimado,
                "status": empresa.status, "origem_lead": empresa.origem_lead,
                "ultima_interacao": empresa.ultima_interacao,
                "proxima_acao": empresa.proxima_acao,
                "data_proxima_acao": empresa.data_proxima_acao,
                "motivo_perdido": empresa.motivo_perdido,
                "temperatura": empresa.temperatura
            }
        )

        if status_mudou:
            conn.execute(
                text("""
                    INSERT INTO empresa_status_historico (
                        historico_id, empresa_id, status_anterior, status_novo, observacao, alterado_em
                    ) VALUES (:id, :empresa_id, :status_anterior, :status_novo, :observacao, NOW())
                """),
                {
                    "id": str(uuid.uuid4()), "empresa_id": empresa_id,
                    "status_anterior": status_anterior, "status_novo": empresa.status,
                    "observacao": empresa.motivo_perdido if empresa.status == "Perdido" else None,
                }
            )
    return {"msg": "Empresa atualizada com sucesso 🚀"}

@app.delete("/empresas/{empresa_id}")
def deletar_empresa(empresa_id: str):
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM contatos WHERE empresa_id = :id"), {"id": empresa_id})
        conn.execute(text("DELETE FROM empresa_status_historico WHERE empresa_id = :id"), {"id": empresa_id})
        result = conn.execute(
            text("DELETE FROM empresas WHERE empresa_id = :id RETURNING empresa_id"),
            {"id": empresa_id}
        ).fetchone()
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
            {"id": empresa_id}
        )
        return [dict(row._mapping) for row in result]

@app.post("/contatos")
def criar_contato(contato: dict):
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO contatos (
                    contato_id, empresa_id, nome, funcao, email, celular, observacoes,
                    prioridade, whatsapp, linkedin, nivel_influencia, decisor,
                    data_ultimo_contato, canal_preferido
                ) VALUES (
                    :id, :empresa_id, :nome, :funcao, :email, :celular, :observacoes,
                    :prioridade, :whatsapp, :linkedin, :nivel_influencia, :decisor,
                    :data_ultimo_contato, :canal_preferido
                )
            """),
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
            }
        )
    return {"msg": "Contato criado com sucesso 🚀"}

@app.put("/contatos/{contato_id}")
def atualizar_contato(contato_id: str, contato: ContatoUpdate):
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT contato_id FROM contatos WHERE contato_id = :id"),
            {"id": contato_id}
        ).fetchone()
        if not result:
            raise HTTPException(404, "Contato não encontrado")
        conn.execute(
            text("""
                UPDATE contatos SET
                    nome = COALESCE(:nome, nome),
                    funcao = COALESCE(:funcao, funcao),
                    email = COALESCE(:email, email),
                    celular = COALESCE(:celular, celular),
                    whatsapp = COALESCE(:whatsapp, whatsapp),
                    linkedin = COALESCE(:linkedin, linkedin),
                    observacoes = COALESCE(:observacoes, observacoes),
                    prioridade = COALESCE(:prioridade, prioridade),
                    nivel_influencia = COALESCE(:nivel_influencia, nivel_influencia),
                    decisor = COALESCE(:decisor, decisor),
                    canal_preferido = COALESCE(:canal_preferido, canal_preferido),
                    data_ultimo_contato = COALESCE(:data_ultimo_contato, data_ultimo_contato)
                WHERE contato_id = :id
            """),
            {
                "id": contato_id,
                "nome": contato.nome, "funcao": contato.funcao, "email": contato.email,
                "celular": contato.celular, "whatsapp": contato.whatsapp, "linkedin": contato.linkedin,
                "observacoes": contato.observacoes, "prioridade": contato.prioridade,
                "nivel_influencia": contato.nivel_influencia, "decisor": contato.decisor,
                "canal_preferido": contato.canal_preferido, "data_ultimo_contato": contato.data_ultimo_contato,
            }
        )
    return {"msg": "Contato atualizado com sucesso 🚀"}

@app.delete("/contatos/{contato_id}")
def deletar_contato(contato_id: str):
    with engine.begin() as conn:
        result = conn.execute(
            text("DELETE FROM contatos WHERE contato_id = :id RETURNING contato_id"),
            {"id": contato_id}
        ).fetchone()
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
                text("""
                    INSERT INTO usuarios (usuario_id, nome, email, telefone, ativo, token_ativacao, data_criacao)
                    VALUES (:usuario_id, :nome, :email, :telefone, FALSE, :token, NOW())
                """),
                {"usuario_id": str(uuid.uuid4()), "nome": usuario.nome, "email": usuario.email,
                 "telefone": usuario.telefone, "token": token_ativacao}
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
            text("""
                UPDATE usuarios SET senha_hash = :senha, ativo = TRUE, token_ativacao = NULL
                WHERE token_ativacao = :token RETURNING usuario_id
            """),
            {"senha": senha_hash, "token": dados.token}
        ).fetchone()
        if not result:
            raise HTTPException(400, "Token inválido")
    return {"msg": "Conta ativada com sucesso 🚀"}

@app.post("/login", response_model=Token)
def login(dados: Login):
    with engine.connect() as conn:
        usuario = conn.execute(
            text("SELECT * FROM usuarios WHERE email = :email"), {"email": dados.email}
        ).fetchone()
    if not usuario:
        raise HTTPException(401, "Usuário não encontrado")
    usuario = dict(usuario._mapping)
    if not usuario["ativo"]:
        raise HTTPException(401, "Conta não ativada")
    if not verificar_senha(dados.senha, usuario["senha_hash"]):
        raise HTTPException(401, "Senha inválida")
    token = criar_token_acesso({"sub": usuario["email"]})
    return {"access_token": token, "token_type": "bearer"}