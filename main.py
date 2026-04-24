# =========================
# IMPORTAÇÕES
# =========================
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext
from datetime import datetime, timedelta
import uuid
import jwt
import os

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig

# =========================
# CONFIG
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("🚨 DATABASE_URL não encontrada!")

SECRET_KEY = "super_secret_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

engine = create_engine(DATABASE_URL)

app = FastAPI()

# =========================
# CORS
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# EMAIL CONFIG
# =========================
conf = ConnectionConfig(
    MAIL_USERNAME="gabrielsantos2411.gs@gmail.com",
    MAIL_PASSWORD="guxehvelkmnosjqd",
    MAIL_FROM="gabrielsantos2411.gs@gmail.com",
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

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

# =========================
# EMAIL
# =========================
async def enviar_email(destino: str, token: str):
    link = f"http://localhost:3000/ativar?token={token}"

    message = MessageSchema(
        subject="Ative sua conta 🚀",
        recipients=[destino],
        body=f"""
        Olá!

        Clique no link abaixo para criar sua senha:

        {link}
        """,
        subtype="plain"
    )

    fm = FastMail(conf)
    await fm.send_message(message)

# =========================
# MODELOS
# =========================
class UsuarioCreate(BaseModel):
    nome: str
    email: EmailStr
    telefone: str | None = None


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
    temperatura: str | None = None


class ContatoCreate(BaseModel):
    empresa_id: str
    nome: str
    funcao: str | None = None
    email: str | None = None
    celular: str | None = None
    observacoes: str | None = None


class AtivarConta(BaseModel):
    token: str
    senha: str


class Login(BaseModel):
    email: EmailStr
    senha: str


class Token(BaseModel):
    access_token: str
    token_type: str


# =========================
# ROTAS
# =========================

@app.get("/")
def home():
    return {"msg": "API rodando 🚀"}


# =========================
# CRIAR USUÁRIO
# =========================
@app.post("/usuarios", status_code=201)
async def criar_usuario(usuario: UsuarioCreate):

    token_ativacao = str(uuid.uuid4())

    try:
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO usuarios (
                        usuario_id,
                        nome,
                        email,
                        telefone,
                        ativo,
                        token_ativacao,
                        data_criacao
                    )
                    VALUES (
                        :usuario_id,
                        :nome,
                        :email,
                        :telefone,
                        FALSE,
                        :token,
                        NOW()
                    )
                """),
                {
                    "usuario_id": str(uuid.uuid4()),
                    "nome": usuario.nome,
                    "email": usuario.email,
                    "telefone": usuario.telefone,
                    "token": token_ativacao
                }
            )

        await enviar_email(usuario.email, token_ativacao)

        return {"msg": "Usuário criado. Verifique seu email 📩"}

    except IntegrityError:
        raise HTTPException(400, "Email já cadastrado")


# =========================
# CRIAR EMPRESA
# =========================
@app.post("/empresas")
def criar_empresa(empresa: EmpresaCreate):

    empresa_id = str(uuid.uuid4())

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO empresas (
                    empresa_id, nome, segmento, porte, cidade,
                    endereco, cep, bairro, regiao, observacoes,
                    cnpj, site, linkedin_empresa, responsavel_principal,
                    ticket_medio_estimado, status, origem_lead,
                    ultima_interacao, proxima_acao, temperatura
                )
                VALUES (
                    :id, :nome, :segmento, :porte, :cidade,
                    :endereco, :cep, :bairro, :regiao, :observacoes,
                    :cnpj, :site, :linkedin_empresa, :responsavel_principal,
                    :ticket_medio_estimado, :status, :origem_lead,
                    :ultima_interacao, :proxima_acao, :temperatura
                )
            """),
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
                "temperatura": empresa.temperatura
            }
        )

    return {
        "msg": "Empresa criada com sucesso 🚀",
        "id": empresa_id
    }


# =========================
# CRIAR CONTATO
# =========================
@app.post("/contatos")
def criar_contato(contato: dict):

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO contatos (
                    contato_id,
                    empresa_id,
                    nome,
                    funcao,
                    email,
                    celular,
                    observacoes,
                    prioridade,
                    whatsapp,
                    linkedin,
                    nivel_influencia,
                    decisor,
                    data_ultimo_contato,
                    canal_preferido
                )
                VALUES (
                    :id,
                    :empresa_id,
                    :nome,
                    :funcao,
                    :email,
                    :celular,
                    :observacoes,
                    :prioridade,
                    :whatsapp,
                    :linkedin,
                    :nivel_influencia,
                    :decisor,
                    :data_ultimo_contato,
                    :canal_preferido
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


# =========================
# ATIVAR CONTA
# =========================
@app.post("/ativar-conta")
def ativar_conta(dados: AtivarConta):

    senha_hash = hash_senha(dados.senha)

    with engine.begin() as conn:
        result = conn.execute(
            text("""
                UPDATE usuarios
                SET senha_hash = :senha,
                    ativo = TRUE,
                    token_ativacao = NULL
                WHERE token_ativacao = :token
                RETURNING usuario_id
            """),
            {
                "senha": senha_hash,
                "token": dados.token
            }
        ).fetchone()

        if not result:
            raise HTTPException(400, "Token inválido")

    return {"msg": "Conta ativada com sucesso 🚀"}


# =========================
# LOGIN
# =========================
@app.post("/login", response_model=Token)
def login(dados: Login):

    with engine.connect() as conn:
        usuario = conn.execute(
            text("SELECT * FROM usuarios WHERE email = :email"),
            {"email": dados.email}
        ).fetchone()

    if not usuario:
        raise HTTPException(401, "Usuário não encontrado")

    usuario = dict(usuario._mapping)

    if not usuario["ativo"]:
        raise HTTPException(401, "Conta não ativada")

    if not verificar_senha(dados.senha, usuario["senha_hash"]):
        raise HTTPException(401, "Senha inválida")

    token = criar_token_acesso({"sub": usuario["email"]})

    return {
        "access_token": token,
        "token_type": "bearer"
    }