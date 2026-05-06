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
ACCESS_TOKEN_EXPIRE_MINUTES = 60

resend.api_key = os.getenv("RESEND_API_KEY")

engine = create_engine(DATABASE_URL)
security = HTTPBearer()

app = FastAPI()

# =========================
# CORS
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
# EMAIL
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
    temperatura: str | None = None

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
# EVENTOS
# =========================
@app.get("/eventos")
def listar_eventos(email: str = Depends(get_current_user)):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM eventos WHERE usuario_email = :email ORDER BY data, hora_inicio"),
            {"email": email}
        )
        eventos = [dict(row._mapping) for row in result]
    return eventos

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
                    titulo = COALESCE(:titulo, titulo),
                    tipo = COALESCE(:tipo, tipo),
                    data = COALESCE(:data, data),
                    hora_inicio = COALESCE(:hora_inicio, hora_inicio),
                    hora_fim = COALESCE(:hora_fim, hora_fim),
                    empresa_id = COALESCE(:empresa_id, empresa_id),
                    empresa_nome = COALESCE(:empresa_nome, empresa_nome),
                    descricao = COALESCE(:descricao, descricao)
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
# EMPRESAS
# =========================
@app.get("/empresas")
def listar_empresas():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM empresas"))
        return [dict(row._mapping) for row in result]

@app.get("/empresas/{empresa_id}")
def buscar_empresa(empresa_id: str):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM empresas WHERE empresa_id = :id"), {"id": empresa_id}
        ).fetchone()
    if not result:
        raise HTTPException(404, "Empresa não encontrada")
    return dict(result._mapping)

@app.post("/empresas")
def criar_empresa(empresa: EmpresaCreate):
    empresa_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO empresas (
                    empresa_id, nome, segmento, porte, cidade, endereco, cep, bairro, regiao,
                    observacoes, cnpj, site, linkedin_empresa, responsavel_principal,
                    ticket_medio_estimado, status, origem_lead, ultima_interacao, proxima_acao, temperatura
                ) VALUES (
                    :id, :nome, :segmento, :porte, :cidade, :endereco, :cep, :bairro, :regiao,
                    :observacoes, :cnpj, :site, :linkedin_empresa, :responsavel_principal,
                    :ticket_medio_estimado, :status, :origem_lead, :ultima_interacao, :proxima_acao, :temperatura
                )
            """),
            {
                "id": empresa_id, "nome": empresa.nome, "segmento": empresa.segmento,
                "porte": empresa.porte, "cidade": empresa.cidade, "endereco": empresa.endereco,
                "cep": empresa.cep, "bairro": empresa.bairro, "regiao": empresa.regiao,
                "observacoes": empresa.observacoes, "cnpj": empresa.cnpj, "site": empresa.site,
                "linkedin_empresa": empresa.linkedin_empresa, "responsavel_principal": empresa.responsavel_principal,
                "ticket_medio_estimado": empresa.ticket_medio_estimado, "status": empresa.status,
                "origem_lead": empresa.origem_lead, "ultima_interacao": empresa.ultima_interacao,
                "proxima_acao": empresa.proxima_acao, "temperatura": empresa.temperatura
            }
        )
    return {"msg": "Empresa criada com sucesso 🚀", "id": empresa_id}

@app.put("/empresas/{empresa_id}")
def atualizar_empresa(empresa_id: str, empresa: EmpresaUpdate):
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT empresa_id FROM empresas WHERE empresa_id = :id"), {"id": empresa_id}
        ).fetchone()
        if not result:
            raise HTTPException(404, "Empresa não encontrada")
        conn.execute(
            text("""
                UPDATE empresas SET
                    nome = COALESCE(:nome, nome), segmento = COALESCE(:segmento, segmento),
                    porte = COALESCE(:porte, porte), cidade = COALESCE(:cidade, cidade),
                    endereco = COALESCE(:endereco, endereco), cep = COALESCE(:cep, cep),
                    bairro = COALESCE(:bairro, bairro), regiao = COALESCE(:regiao, regiao),
                    observacoes = COALESCE(:observacoes, observacoes), cnpj = COALESCE(:cnpj, cnpj),
                    site = COALESCE(:site, site), linkedin_empresa = COALESCE(:linkedin_empresa, linkedin_empresa),
                    responsavel_principal = COALESCE(:responsavel_principal, responsavel_principal),
                    ticket_medio_estimado = COALESCE(:ticket_medio_estimado, ticket_medio_estimado),
                    status = COALESCE(:status, status), origem_lead = COALESCE(:origem_lead, origem_lead),
                    ultima_interacao = COALESCE(:ultima_interacao, ultima_interacao),
                    proxima_acao = COALESCE(:proxima_acao, proxima_acao),
                    temperatura = COALESCE(:temperatura, temperatura)
                WHERE empresa_id = :id
            """),
            {
                "id": empresa_id, "nome": empresa.nome, "segmento": empresa.segmento,
                "porte": empresa.porte, "cidade": empresa.cidade, "endereco": empresa.endereco,
                "cep": empresa.cep, "bairro": empresa.bairro, "regiao": empresa.regiao,
                "observacoes": empresa.observacoes, "cnpj": empresa.cnpj, "site": empresa.site,
                "linkedin_empresa": empresa.linkedin_empresa, "responsavel_principal": empresa.responsavel_principal,
                "ticket_medio_estimado": empresa.ticket_medio_estimado, "status": empresa.status,
                "origem_lead": empresa.origem_lead, "ultima_interacao": empresa.ultima_interacao,
                "proxima_acao": empresa.proxima_acao, "temperatura": empresa.temperatura
            }
        )
    return {"msg": "Empresa atualizada com sucesso 🚀"}

@app.delete("/empresas/{empresa_id}")
def deletar_empresa(empresa_id: str):
    with engine.begin() as conn:
        result = conn.execute(
            text("DELETE FROM empresas WHERE empresa_id = :id RETURNING empresa_id"), {"id": empresa_id}
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
            text("SELECT * FROM contatos WHERE empresa_id = :id"), {"id": empresa_id}
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
                "empresa_id": contato.get("empresa_id"), "nome": contato.get("nome"),
                "funcao": contato.get("funcao"), "email": contato.get("email"),
                "celular": contato.get("celular"), "observacoes": contato.get("observacoes"),
                "prioridade": contato.get("prioridade"), "whatsapp": contato.get("whatsapp"),
                "linkedin": contato.get("linkedin"), "nivel_influencia": contato.get("nivel_influencia"),
                "decisor": contato.get("decisor"), "data_ultimo_contato": contato.get("data_ultimo_contato"),
                "canal_preferido": contato.get("canal_preferido"),
            }
        )
    return {"msg": "Contato criado com sucesso 🚀"}

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