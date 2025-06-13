import os
import sys
import zipfile
import yaml
import shutil
import pandas as pd
import numpy as np
from pandas.errors import EmptyDataError
from datetime import datetime
from dotenv import load_dotenv
from colorama import init, Fore, Style

from langchain_perplexity.chat_models import ChatPerplexity
from langchain.prompts import PromptTemplate
from langchain.output_parsers import ResponseSchema
from langchain.output_parsers import StructuredOutputParser

def timestamp_time() -> str:
    return datetime.now().strftime("%H:%M:%S")

def current_date_str() -> str:
    return datetime.now().strftime("%d/%m/%Y")

def log_info(msg: str):
    t = timestamp_time()
    header_data()
    print(f"{Fore.CYAN}[{t}] Sistema: {msg}{Style.RESET_ALL}")

def log_success(msg: str):
    t = timestamp_time()
    header_data()
    print(f"{Fore.GREEN}[{t}] Sistema: {msg}{Style.RESET_ALL}")

def log_warning(msg: str):
    t = timestamp_time()
    header_data()
    print(f"{Fore.YELLOW}[{t}] Sistema: {msg}{Style.RESET_ALL}")

def log_error(msg: str):
    t = timestamp_time()
    header_data()
    print(f"{Fore.RED}[{t}] Sistema: {msg}{Style.RESET_ALL}")

def agent_response(msg: str):
    t = timestamp_time()
    header_data()
    print(f"{Fore.GREEN}[{t}] Agente: {msg}{Style.RESET_ALL}")

LOG_FUNCS = {
    "info":    log_info,
    "success": log_success,
    "warning": log_warning,
    "error":   log_error,
}

WIDTH_CLI = shutil.get_terminal_size().columns# shutil.get_terminal_size((80, 20)).columns

LAST_DATE = ''

def setup_llm():
    load_dotenv()
    PPLX_API_KEY = os.getenv("PPLX_API_KEY")

    return ChatPerplexity(
        api_key=PPLX_API_KEY,
        model="sonar",
        temperature=0,
        max_tokens=200
    )

def sync_csvs_overwrite(source_path: str, dest_folder: str = "files"):
    os.makedirs(dest_folder, exist_ok=True)
    messages = []
    if os.path.isfile(source_path) and source_path.lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(source_path, "r") as zf:
                count = 0
                for member in zf.namelist():
                    if member.lower().endswith(".csv"):
                        zf.extract(member, dest_folder)
                        count += 1
            if count:
                messages.append(("success",
                    f"{count} arquivo(s) CSV extraído(s) de '{source_path}'."
                ))
            else:
                messages.append(("warning",
                    f"Nenhum CSV encontrado dentro de '{source_path}'."
                ))
        except Exception as e:
            messages.append(("error",
                f"Falha ao extrair ZIP '{source_path}': {e}"
            ))

    elif os.path.isdir(source_path):
        copied = 0
        for fname in os.listdir(source_path):
            if fname.lower().endswith(".csv"):
                shutil.copy(
                    os.path.join(source_path, fname),
                    os.path.join(dest_folder, fname)
                )
                copied += 1
        if copied:
            messages.append(("success",
                f"{copied} arquivo(s) CSV copiado(s) de '{source_path}'."
            ))
        else:
            messages.append(("warning",
                f"Nenhum CSV encontrado em '{source_path}'."
            ))
    else:
        messages.append(("error",
            f"'{source_path}' não é um .zip nem um diretório válido."
        ))

    return messages

def load_csv_data(folder="files"):
    csv_headers = {}
    dataframes = {}
    messages = []

    for filename in os.listdir(folder):
        if not filename.lower().endswith(".csv"):
            continue

        path = os.path.join(folder, filename)
        try:
            df = pd.read_csv(path)
        except EmptyDataError:
            messages.append((
                "warning",
                f"'{filename}' está vazio ou sem cabeçalhos e foi ignorado."
            ))
            continue
        except Exception as e:
            messages.append((
                "warning",
                f"Não foi possível ler '{filename}': {e}. Ignorando."
            ))
            continue

        if df.columns.empty:
            messages.append((
                "warning",
                f"'{filename}' não possui colunas e foi ignorado."
            ))
            continue

        csv_headers[filename] = list(df.columns)
        dataframes[filename] = df

    if not dataframes:
        messages.append((
            "error",
            f"Nenhum CSV válido encontrado em '{folder}'."
        ))

    return csv_headers, dataframes, messages

def output_schema():
    schema_pandas_query = ResponseSchema(
        name="pandas_query",
        type="string",
        description="A single line of pandas (DataFrames) code",
    )
    response_schema = [schema_pandas_query]
    return StructuredOutputParser.from_response_schemas(response_schema)

def main_prompt_template(output):
    return PromptTemplate.from_template(
        """
        You are a data scientist. Generate ONLY a single line of Python code, starting with 'result ='.
        Use ONLY pandas DataFrames from the preloaded 'dfs' dictionary to answer the user's question below.
        Do NOT use 'pd.read_csv' or open files directly.
        Do NOT write explanations or print statements.

        If the user question is not related to invoices or fiscal notes, do not attempt to answer.
          - Instead, respond with the following standard query, which always returns empty data:
          - result = 0
          - Do not generate any other type of code or explanation in this case.

        - All CSV files have already been loaded into pandas DataFrames and mapped in the Python dictionary called 'dfs'.
        - The key of each DataFrame in 'dfs' is the original CSV file name (including the .csv extension).
        - NEVER use 'pd.read_csv' or any file reading method. Only use the preloaded DataFrames via 'dfs'.
        - Each CSV file name reflects its position and role in the data hierarchy. Files like 'Cabecalho' are master records; files like 'Itens' are detail records related to the master file.
        - If the column 'CHAVE DE ACESSO' (Access Key) appears in multiple files and must be used as a join/merge key when combining data from more than one DataFrame.
        - Always use the exact file and column names as provided below.
        Whenever the user's question involves locations, states, or countries, always perform lookups and filters using BOTH the abbreviation and the full name for each location. 
        For example: 
        - if the question mentions "SP", also check for "São Paulo"; 
        - if it mentions "RJ", also check for "Rio de Janeiro". 
        This rule applies to all locations, states, provinces, and countries.
        
        {context}

        {output}

        {retry_info}

        Exemples of valid code:
        Q: "Qual o valor total das notas fiscais?"
        A: result = dfs["notas.csv"]["VALOR"].sum()

        Q: "Quais produtos o cliente Ana comprou em fevereiro?"
        A: result = dfs["itens.csv"].loc[(dfs["itens.csv"]["CLIENTE"] == "Ana") & (dfs["itens.csv"]["DATA"].str.contains("/02/")), "PRODUTO"].unique().tolist()

        User question (in Portuguese): "{question}"
        
        """,partial_variables={"output": output}
    )

def headers_context(csv_headers):
    return (
        "Available CSV files and columns:\n"
        + "\n".join([f"{fname}: {cols}" for fname, cols in csv_headers.items()])      
    )  

def validate_code(result):
    if "import" in result or "__" in result:
        raise ValueError("Unsafe code detected!")
         
def format_answer(result):

    if isinstance(result, pd.DataFrame) and result.empty:
        return "Não foram encontrados resultados para sua consulta."

    if isinstance(result, pd.DataFrame):
        result = result.to_dict(orient="records")
    elif isinstance(result, pd.Series):
        result = result.to_dict()

    if isinstance(result, (str, int, float, bool)):
        return f"O resultado para sua consulta é {result}"

    if isinstance(result, (list, tuple, set, np.ndarray)):
        seq = list(result)
        if seq and all(isinstance(x, (str, int, float, bool)) for x in seq):
            return "\n".join(f"- {x}" for x in seq)
        
    return "\n" + yaml.dump(result, allow_unicode=True)

def safe_search(
    llm, user_question, context, output, dataframes, max_retries=2
):
    pandas_query = None
    error = None

    prompt_template = main_prompt_template(output=output.get_format_instructions())

    for attempt in range(max_retries):
        if attempt == 0:
            retry_info = ""
        else:
            retry_info = (
                f"PREVIOUS QUERY:\n{pandas_query}\n"
                f"ERROR:\n{error}\n"
                "Analyze the error above and generate a NEW, corrected pandas code line, avoiding the same mistake."
            )

        formatted_prompt = prompt_template.format(
            context=context,
            question=user_question,
            retry_info=retry_info
        )

        try:
            llm_code_response = llm.invoke(formatted_prompt)
            result_dict = output.parse(llm_code_response.content)
            pandas_query = result_dict["pandas_query"]

            validate_code(pandas_query)
            local_vars = {"dfs": dataframes}
            exec(pandas_query, {}, local_vars)
            result = local_vars.get("result")

            if isinstance(result, pd.DataFrame) and result.empty:
                raise ValueError("A consulta não encontrou nenhum resultado.")
            if result is None:
                raise ValueError("A consulta não retornou um valor válido.")

            return format_answer(result)

        except Exception as e:
            error = e 
            print(f"[Tentativa {attempt+1}] Erro: {e}")
            if attempt == max_retries - 1:
                return (
                    "Desculpe, não consegui encontrar um resultado para sua consulta. "
                    "Tente reformular sua pergunta ou envie uma dúvida diferente."
                )

def print_header():
    title = "AGENTE CSV DE NOTAS FISCAIS"
    subtitle = "Faça perguntas sobre os dados das notas fiscais."
    footer = "Use Ctrl+C ou Ctrl+D para sair a qualquer momento."

    border = "=" * (WIDTH_CLI-1)

    print(Fore.MAGENTA + border.center(WIDTH_CLI) + Style.RESET_ALL)
    print(Fore.MAGENTA + title.center(WIDTH_CLI) + Style.RESET_ALL)
    print(Fore.MAGENTA + border.center(WIDTH_CLI) + Style.RESET_ALL)
    print(subtitle.center(WIDTH_CLI))
    print(footer.center(WIDTH_CLI) + "\n")

def header_data():
    curr_date = current_date_str()
    global LAST_DATE
    if curr_date > LAST_DATE:
        LAST_DATE = curr_date
        print(Fore.MAGENTA + LAST_DATE.rjust(WIDTH_CLI) + Style.RESET_ALL)

def preload_csv_menu(dest_folder="files"):
    os.makedirs(dest_folder, exist_ok=True)
    t = timestamp_time()
    while True:
        existing = [
            f for f in os.listdir(dest_folder)
            if f.lower().endswith(".csv")
        ]
        try:
            if existing:
                log_info(f"CSV encontrados em '{dest_folder}':")
                for f in existing:
                    print(f"  - {f}")
                
                choice = input(f"{Fore.CYAN}[{t}] Sistema: Deseja incluir mais arquivos? (s/n): {Style.RESET_ALL}").strip().lower()
                if choice == 'n':
                    break
                elif choice != 's':
                    log_warning("Resposta inválida. Digite 's' ou 'n'.")
                    continue
            else:
                log_info(f"Nenhum CSV encontrado em '{dest_folder}'.")
                
            src = input(f"{Fore.CYAN}[{t}] Sistema: Informe o PATH do ZIP/pasta com CSVs: {Style.RESET_ALL}").strip()
            msgs = sync_csvs_overwrite(src, dest_folder)
        except (EOFError, KeyboardInterrupt):
            sys.stdout.write("\n")
            break
        
        process_messages(msgs)

def run_chat(llm, context, output, dataframes): 
    while True:
        try:
            user_question = input(f"{Fore.CYAN}Você:{Style.RESET_ALL} ").strip()
        except (EOFError, KeyboardInterrupt):
            sys.stdout.write("\n")
            user_question = 'sair'

        t = timestamp_time()
        sys.stdout.write("\033[A\033[2K")
        sys.stdout.flush()
        header_data()
        sys.stdout.write(f"{Fore.CYAN}[{t}] Você: {user_question}{Style.RESET_ALL}\n")

        if len(user_question) < 4:
            log_warning("Pergunta muito curta. Digite ao menos 4 caracteres.")
            continue

        if user_question.lower() in ('sair', 'exit', 'quit'):
            log_warning("Até logo! 👋")
            break

        try:
            answer = safe_search(llm, user_question, context, output, dataframes)
            agent_response(answer)
        except Exception as e:
            log_error(f"Erro ao responder '{user_question}': {e}")   

def main():
    init(autoreset=True)
    print_header()
    header_data()
    preload_csv_menu(dest_folder="files")
    csv_headers, dataframes, load_msgs = load_csv_data(folder="files")
    llm = setup_llm();
    output = output_schema()
    context = headers_context(csv_headers);
    process_messages(load_msgs)
    run_chat(llm, context, output, dataframes)

def process_messages(messages, stop_on_error=False):
    for level, text in messages:
        func = LOG_FUNCS.get(level, log_error)
        func(text)

        if stop_on_error and func is log_error:
            return

if __name__ == "__main__":
    main()
