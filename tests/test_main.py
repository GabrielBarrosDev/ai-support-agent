
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Usa um banco temporário para não alterar
    # o banco real do projeto durante os testes.
    banco_teste = tmp_path / "test_conversas.db"

    monkeypatch.setattr(main, "DB_NAME", str(banco_teste))
    main.criar_banco()

    return TestClient(main.app)


def test_home(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "mensagem": "AI Support Agent funcionando!"
    }


def test_chat_salva_mensagens(client, monkeypatch):
    # Simula a resposta do Ollama, sem carregar o modelo.
    def chat_falso(**kwargs):
        return SimpleNamespace(
            message=SimpleNamespace(content="Olá! Resposta de teste.")
        )

    monkeypatch.setattr(main, "chat", chat_falso)

    response = client.post(
        "/chat",
        json={"mensagem": "Olá, agente!"}
    )

    assert response.status_code == 200

    dados = response.json()

    assert dados["conversa_id"]
    assert dados["resposta"] == "Olá! Resposta de teste."

    # Confirma que a mensagem do usuário e a resposta
    # do assistente foram salvas no banco temporário.
    with sqlite3.connect(main.DB_NAME) as conn:
        mensagens = conn.execute(
            """
            SELECT papel, conteudo
            FROM mensagens
            WHERE conversa_id = ?
            ORDER BY id
            """,
            (dados["conversa_id"],)
        ).fetchall()

    assert mensagens == [
        ("user", "Olá, agente!"),
        ("assistant", "Olá! Resposta de teste.")
    ]


def test_obter_conversa(client, monkeypatch):
    def chat_falso(**kwargs):
        return SimpleNamespace(
            message=SimpleNamespace(content="Tudo certo!")
        )

    monkeypatch.setattr(main, "chat", chat_falso)

    resposta_chat = client.post(
        "/chat",
        json={"mensagem": "Teste do histórico"}
    )

    conversa_id = resposta_chat.json()["conversa_id"]

    response = client.get(f"/conversas/{conversa_id}")

    assert response.status_code == 200

    dados = response.json()

    assert dados["conversa_id"] == conversa_id
    assert len(dados["mensagens"]) == 2
    assert dados["mensagens"][0]["papel"] == "user"
    assert dados["mensagens"][0]["conteudo"] == "Teste do histórico"
    assert dados["mensagens"][1]["papel"] == "assistant"
    assert dados["mensagens"][1]["conteudo"] == "Tudo certo!"

def test_erro_quando_ollama_falha(client, monkeypatch):
    def chat_com_erro(**kwargs):
        raise RuntimeError("Ollama indisponível")

    monkeypatch.setattr(main, "chat", chat_com_erro)

    response = client.post(
        "/chat",
        json={"mensagem": "Olá"}
    )

    assert response.status_code == 502
    assert "Erro ao processar a mensagem" in response.json()["detail"]


def test_historico_inclui_mensagens_anteriores(client, monkeypatch):
    chamadas = []

    def chat_falso(**kwargs):
        chamadas.append(kwargs)

        return SimpleNamespace(
            message=SimpleNamespace(
                content=f"Resposta {len(chamadas)}"
            )
        )

    monkeypatch.setattr(main, "chat", chat_falso)

    # Primeira mensagem: cria uma conversa.
    primeira = client.post(
        "/chat",
        json={"mensagem": "Meu nome é Gabriel"}
    )

    conversa_id = primeira.json()["conversa_id"]

    # Segunda mensagem: continua a mesma conversa.
    segunda = client.post(
        "/chat",
        json={
            "mensagem": "Qual é o meu nome?",
            "conversa_id": conversa_id
        }
    )

    assert segunda.status_code == 200

    mensagens_enviadas = chamadas[1]["messages"]

    assert any(
        m["role"] == "user"
        and m["content"] == "Meu nome é Gabriel"
        for m in mensagens_enviadas
    )

    assert any(
        m["role"] == "assistant"
        and m["content"] == "Resposta 1"
        for m in mensagens_enviadas
    )

    assert mensagens_enviadas[-1] == {
        "role": "user",
        "content": "Qual é o meu nome?"
    }


def test_conversa_inexistente_retorna_lista_vazia(client):
    response = client.get("/conversas/conversa-que-nao-existe")

    assert response.status_code == 200
    assert response.json() == {
        "conversa_id": "conversa-que-nao-existe",
        "mensagens": []
    }

