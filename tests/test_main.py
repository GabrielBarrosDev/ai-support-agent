
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

def test_faq_e_enviada_ao_ollama(client, monkeypatch):
    chamadas = []

    def chat_falso(**kwargs):
        chamadas.append(kwargs)

        return SimpleNamespace(
            message=SimpleNamespace(
                content="Consulte o canal oficial de atendimento."
            )
        )

    monkeypatch.setattr(main, "chat", chat_falso)

    response = client.post(
        "/chat",
        json={"mensagem": "Como entro em contato com o suporte?"}
    )
    
    assert response.status_code == 200
    assert len(chamadas) == 1

    mensagens_enviadas = chamadas[0]["messages"]
    mensagem_sistema = mensagens_enviadas[0]["content"]

    print(repr(mensagem_sistema))

    assert "BASE DE CONHECIMENTO" in mensagem_sistema
    assert "Como posso entrar em contato com o suporte?" in mensagem_sistema
    assert "Esqueci minha senha" not in mensagem_sistema

def test_instrui_agente_a_nao_inventar_respostas(client, monkeypatch):
    chamadas = []

    def chat_falso(**kwargs):
        chamadas.append(kwargs)

        return SimpleNamespace(
            message=SimpleNamespace(
                content=(
                    "Não encontrei essa informação na base "
                    "de conhecimento. Recomendo contatar "
                    "o suporte humano."
                )
            )
        )

    monkeypatch.setattr(main, "chat", chat_falso)

    response = client.post(
        "/chat",
        json={"mensagem": "A empresa oferece reembolso em 24 horas?"}
    )

    assert response.status_code == 200

    mensagens = chamadas[0]["messages"]
    instrucao_sistema = mensagens[0]["content"]

    assert "Não invente políticas" in instrucao_sistema
    assert "não encontrou essa informação" in instrucao_sistema
    assert "BASE DE CONHECIMENTO" in instrucao_sistema
    assert "recomende contatar o suporte humano" in instrucao_sistema

def test_buscar_faq_sobre_senha():
    resultado = main.buscar_na_faq(
        "Esqueci minha senha, como faço?"
    )

    assert "Esqueci minha senha" in resultado
    assert "tela de login" in resultado


def test_buscar_faq_sem_informacao_relevante():
    resultado = main.buscar_na_faq(
        "Qual é o endereço da empresa?"
    )

    assert (
        "Nenhuma informação relevante foi encontrada"
        in resultado
    )

def test_buscar_faq_com_termos_relacionados():
    resultado = main.buscar_na_faq(
        "Não consigo acessar minha conta"
    )

    assert "Esqueci minha senha" in resultado
    assert "tela de login" in resultado


def test_buscar_faq_sobre_prazo_de_resposta():
    resultado = main.buscar_na_faq(
        "Quanto tempo demora para responder?"
    )

    assert "Quanto tempo demora para receber uma resposta?" in resultado


def test_buscar_faq_sobre_protocolo():
    resultado = main.buscar_na_faq(
        "Como acompanhar meu protocolo?"
    )

    assert "Como posso acompanhar minha solicitacao?" in resultado


def test_buscar_faq_quando_usuario_nao_consegue_acessar_conta():
    resultado = main.buscar_na_faq(
        "Não consigo acessar minha conta"
    )

    assert "Esqueci minha senha" in resultado
    assert "tela de login" in resultado

def test_normalizar_texto_remove_acentos():
    resultado = main.normalizar_texto("Solicitação de Acesso")

    assert resultado == "solicitacao de acesso"


def test_normalizar_texto_converte_para_minusculas():
    resultado = main.normalizar_texto("SENHA E SUPORTE")

    assert resultado == "senha e suporte"

def test_buscar_faq_sem_acentos():
    resultado = main.buscar_na_faq(
        "Como acompanho minha solicitacao?"
    )

    assert "acompanhar minha solicitacao" in (
        main.normalizar_texto(resultado)
    )
    assert "protocolo" in main.normalizar_texto(resultado)

def test_buscar_faq_sobre_endereco_inexistente():
    resultado = main.buscar_na_faq(
        "Qual é o endereço físico da empresa?"
    )

    assert resultado == (
        "Nenhuma informação relevante foi encontrada "
        "na base de conhecimento."
    )






