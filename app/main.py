
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from ollama import chat
import sqlite3
import uuid
from pathlib import Path

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent.parent
DB_NAME = str(BASE_DIR / "conversas.db")
FAQ_PATH = BASE_DIR / "documentos" / "faq.txt"


# Cria a tabela do banco de dados
def criar_banco():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mensagens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversa_id TEXT NOT NULL,
                papel TEXT NOT NULL,
                conteudo TEXT NOT NULL,
                data DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

def carregar_faq():
    if not FAQ_PATH.exists():
        raise FileNotFoundError(
            f"Arquivo de FAQ não encontrado: {FAQ_PATH}"
        )

    return FAQ_PATH.read_text(encoding="utf-8")


def buscar_na_faq(pergunta: str) -> str:
    faq = carregar_faq()

    secoes = faq.split("\n\n")

    termos_relacionados = {
        "senha": ["senha", "acessar", "acesso", "login", "conta"],
        "acesso": ["senha", "acessar", "acesso", "login", "conta"],
        "conta": ["senha", "acessar", "acesso", "login", "conta"],
        "suporte": ["suporte", "atendimento", "contato", "ajuda"],
        "ajuda": ["suporte", "atendimento", "contato", "ajuda"],
        "prazo": ["prazo", "tempo", "demora", "resposta"],
        "resposta": ["prazo", "tempo", "demora", "resposta"],
        "solicitação": ["solicitação", "protocolo", "acompanhar"],
        "solicitacao": ["solicitacao", "protocolo", "acompanhar"],
    }

    palavras_pergunta = set(pergunta.lower().split())
    palavras_busca = set(palavras_pergunta)

    for palavra in palavras_pergunta:
        palavras_busca.update(termos_relacionados.get(palavra, []))

    melhor_secao = ""
    maior_pontuacao = 0

    for secao in secoes:
        secao_lower = secao.lower()

        pontuacao = sum(
            1
            for palavra in palavras_busca
            if len(palavra) > 2 and palavra in secao_lower
        )

        if pontuacao > maior_pontuacao:
            maior_pontuacao = pontuacao
            melhor_secao = secao

    if maior_pontuacao == 0:
        return (
            "Nenhuma informação relevante foi encontrada "
            "na base de conhecimento."
        )

    return melhor_secao


criar_banco()


class ChatRequest(BaseModel):
    mensagem: str
    conversa_id: str | None = None


@app.get("/")
def home():
    return {"mensagem": "AI Support Agent funcionando!"}


@app.post("/chat")
def chat_endpoint(request: ChatRequest):
    try:
        # Cria uma conversa, se necessário
        conversa_id = request.conversa_id or str(uuid.uuid4())

        # Recupera as últimas 10 mensagens
        with sqlite3.connect(DB_NAME) as conn:
            conn.row_factory = sqlite3.Row

            mensagens = conn.execute(
                """
                SELECT papel, conteudo
                FROM mensagens
                WHERE conversa_id = ?
                ORDER BY id DESC
                LIMIT 10
                """,
                (conversa_id,)
            ).fetchall()

            mensagens = list(reversed(mensagens))

            # Salva a mensagem do usuário
            conn.execute(
                """
                INSERT INTO mensagens (conversa_id, papel, conteudo)
                VALUES (?, ?, ?)
                """,
                (conversa_id, "user", request.mensagem)
            )

        # Prepara o contexto para a IA
        historico = [
            {
                "role": mensagem["papel"],
                "content": mensagem["conteudo"]
            }
            for mensagem in mensagens
        ]

        historico.append({
            "role": "user",
            "content": request.mensagem
        })

        faq = buscar_na_faq(request.mensagem)

        
        response = chat(
            model="llama3.1:8b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Você é um assistente de atendimento "
                        "educado e prestativo. Responda em "
                        "português do Brasil.\n\n"
                        "REGRAS IMPORTANTES:\n"
                        "1. Use a base de conhecimento como fonte "
                        "principal para responder às perguntas.\n"
                        "2. Não invente políticas, prazos, contatos "
                        "ou procedimentos.\n"
                        "3. Se a base não contiver informação "
                        "suficiente para responder, diga claramente "
                        "que não encontrou essa informação e "
                        "recomende contatar o suporte humano.\n"
                        "4. Não sugira canais, contatos, links ou "
                        "procedimentos que não estejam confirmados "
                        "na base de conhecimento.\n"
                        "5. Diferencie informações confirmadas de "
                        "informações que não estão disponíveis.\n\n"
                        "BASE DE CONHECIMENTO:\n"
                        f"{faq}"
                    )
                },
                *historico
            ]
        )


        resposta = response.message.content

        # Salva a resposta da IA
        with sqlite3.connect(DB_NAME) as conn:
            conn.execute(
                """
                INSERT INTO mensagens (conversa_id, papel, conteudo)
                VALUES (?, ?, ?)
                """,
                (conversa_id, "assistant", resposta)
            )

        return {
            "conversa_id": conversa_id,
            "resposta": resposta
        }

    except Exception as e:
        import traceback
        traceback.print_exc()

        raise HTTPException(
            status_code=502,
            detail=f"Erro ao processar a mensagem: {e}"
        )


@app.get("/conversas/{conversa_id}")
def obter_conversa(conversa_id: str):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row

        mensagens = conn.execute(
            """
            SELECT papel, conteudo, data
            FROM mensagens
            WHERE conversa_id = ?
            ORDER BY id
            """,
            (conversa_id,)
        ).fetchall()

    return {
        "conversa_id": conversa_id,
        "mensagens": [dict(m) for m in mensagens]
    }