# CSV Agente

Um assistente inteligente para análise de dados de notas fiscais eletrônicas em arquivos CSV. Permite fazer perguntas em português sobre os dados fiscais direto pelo terminal, com respostas precisas via inteligência artificial.

## Pré-requisitos

- Python 3.11 ou superior
- Git (opcional, para clonar o repositório)

## Instalação

1. **Clone o repositório** (ou faça o download dos arquivos):

2. **(Opcional) Crie um ambiente virtual:**

   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate   # No Windows: .venv\Scripts\activate
   ```

3. **Instale as dependências:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure a chave da API Perplexity**  
   Crie um arquivo `.env` na raiz do projeto com o conteúdo:

   ```bash
   PPLX_API_KEY=SEU_TOKEN_AQUI
   ```

## Como rodar

Execute o script principal no terminal:

```bash
python main.py
```

Siga as instruções para carregar seus arquivos CSV e comece a fazer perguntas!

---
