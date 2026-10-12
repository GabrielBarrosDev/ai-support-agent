
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from ollama import chat
import sqlite3
import uuid

app = FastAPI()

DB_NAME = "conversas.db"


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

        response = chat(
            model="llama3.1:8b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Você é um assistente de atendimento "
                        "educado e prestativo. Responda em "
                        "português do Brasil."
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