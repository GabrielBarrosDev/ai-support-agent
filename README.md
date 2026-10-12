# AI Support Agent

Agente de atendimento conversacional desenvolvido em Python, com FastAPI, SQLite e Ollama. O projeto permite enviar mensagens para um modelo de linguagem, manter o histórico de conversas e recuperar mensagens anteriores por identificador de conversa.

**Status:** Em desenvolvimento.

## Tecnologias utilizadas

- **Python** — linguagem principal.
- **FastAPI** — criação dos endpoints da API.
- **Pydantic** — validação dos dados recebidos.
- **SQLite** — armazenamento do histórico de mensagens.
- **Ollama** — integração com o modelo de linguagem `llama3.1:8b`.
- **UUID** — geração de identificadores únicos para conversas.

## Funcionalidades implementadas

- Endpoint inicial para verificar se a API está funcionando.
- Endpoint para enviar mensagens ao assistente.
- Geração de um identificador para novas conversas.
- Armazenamento das mensagens do usuário e das respostas do assistente.
- Recuperação das últimas 10 mensagens para fornecer contexto ao modelo.
- Consulta ao histórico completo de uma conversa.
- Tratamento de erros durante o processamento das mensagens.

## Estrutura do projeto

```text
ai-support-agent/
├── app/
│   ├── __init__.py
│   └── main.py
├── documentos/
│   └── faq.txt
├── .gitignore
└── README.md
```

O banco de dados `conversas.db` é criado localmente durante a inicialização da aplicação e não é versionado no Git.

## Pré-requisitos

- Python instalado.
- Git instalado.
- Ollama instalado e em execução.
- Modelo `llama3.1:8b` disponível no Ollama.

## Instalação e execução

### 1. Clonar o repositório

```bash
git clone https://github.com/GabrielBarrosDev/ai-support-agent.git
cd ai-support-agent
```

### 2. Criar e ativar um ambiente virtual

No Windows, usando PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Instalar as dependências

```bash
pip install fastapi "uvicorn[standard]" ollama
```

### 4. Baixar o modelo de linguagem

Com o Ollama instalado, execute:

```bash
ollama pull llama3.1:8b
```

Mantenha o Ollama em execução antes de utilizar o endpoint de chat.

### 5. Iniciar a API

Na raiz do projeto, execute:

```bash
uvicorn app.main:app --reload
```

A API estará disponível em:

`http://127.0.0.1:8000`

A documentação interativa do FastAPI poderá ser acessada em:

`http://127.0.0.1:8000/docs`

## Endpoints

### `GET /`

Verifica se a aplicação está funcionando.

### `POST /chat`

Envia uma mensagem ao assistente.

Exemplo de requisição:

```json
{
  "mensagem": "Olá! Como você pode me ajudar?"
}
```

Para continuar uma conversa existente, envie também o `conversa_id` retornado pela API:

```json
{
  "mensagem": "Pode explicar melhor?",
  "conversa_id": "ID_DA_CONVERSA"
}
```

A resposta contém o identificador da conversa e o texto gerado pelo modelo.

### `GET /conversas/{conversa_id}`

Recupera as mensagens armazenadas para uma conversa específica, incluindo o papel de cada mensagem, seu conteúdo e a data registrada no banco de dados.

## Próximas melhorias

- Utilizar o conteúdo da pasta `documentos` como base de conhecimento para respostas.
- Melhorar a validação e o tratamento de erros.
- Adicionar testes automatizados.
- Implementar mecanismos de configuração e monitoramento.
- Evoluir a organização da aplicação conforme novas funcionalidades forem adicionadas.

## Autor

**Gabriel Barros dos Santos**

- [GitHub](https://github.com/GabrielBarrosDev)
- [LinkedIn](https://www.linkedin.com/in/gabriel-barros-87a817359/)
