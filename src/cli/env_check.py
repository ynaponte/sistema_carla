import ollama
import os
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from dotenv import load_dotenv

console = Console()

def check_ollama_setup(model_name:str) -> bool:
  """Verifica se o serviço Ollama está rodando e se o modelo especificado está instalado."""
  # --- 1. VERIFICAR SE O OLLAMA ESTÁ RODANDO ---
  try:
    client = ollama.Client()
    installed_models_data = client.list()
  except Exception as ex:
    error_panel = Panel(
      Text.assemble(
        ("Não foi possível conectar ao serviço do Ollama.\n\n", "white"),
        ("Verifique se o aplicativo do Ollama está em execução e acessível em ", "white"),
        ("http://localhost:11434", "cyan"),
        (".\n\n", "white"),
        ("Erro original: ", "dim white"),
        (str(ex), "dim white")
      ),
      title="[bold red]Ollama Inacessível[/bold red]",
      border_style="red"
    )
    console.print(error_panel)
    return False
  
  console.print(":white_check_mark: [bold green]Serviço Ollama está rodando.[/bold green]")
  # --- 2. VERIFICAR SE O MODELO ESTÁ INSTALADO ---
  
  # Normaliza o nome do modelo: remove o prefixo "ollama/" e garante que há uma tag.
  model_name_for_api = model_name.split('/')[-1]

  # Extrai apenas os nomes dos modelos instalados
  installed_model_names = [model['model'] for model in installed_models_data['models']]

  if model_name_for_api not in installed_model_names:
    error_panel = Panel(
      Text.assemble(
        ("O modelo especificado no seu arquivo .env não foi encontrado no Ollama.\n\n", "white"),
        ("Modelo procurado: ", "white"),
        (model_name_for_api, "bold yellow"),
        ("\n\nCertifique-se que ele está ", "white"),
        ("instalado ", "bold yellow"),
        ("e foi ", "white"),
        ("especificado ", "bold yellow"),
        ("corretamente", "white")
      ),
      title="[bold red]Modelo Não Encontrado[/bold red]",
      border_style="red"
    )
    console.print(error_panel)
    return False
  
  console.print(f":white_check_mark: [bold green]Modelo '{model_name_for_api}' encontrado.[/bold green]")
  return True

def check_and_load_dotenv() -> bool:
  """
  Verifica o .env. Se não existir, cria um modelo. Se existir, valida seu conteúdo.
  """
  if not os.path.exists(".env"):
    # O arquivo não existe, então vamos criá-lo para o usuário.
    dotenv_template = (
      "# Arquivo de configuração de ambiente para o CARLA\n"
      "# Por favor, preencha as variáveis abaixo com suas credenciais.\n\n"
      'MODEL=ollama/<<NOME-DO-MODELO>>\n'
      'CONTEXT_LENGTH=<<JANELA-DE-CONTEXTO>>\n'
    )
    
    with open(".env", "w", encoding="utf-8") as f:
      f.write(dotenv_template)
    
    action_panel = Panel(
      Text.assemble(
        ("O arquivo de ambiente (.env) não foi encontrado.\n\n", "white"),
        ("✔ ", "bold green"),
        ("Um modelo foi criado para você com o nome ", "white"),
        (".env", "bold yellow"),
        (".\n\n", "white"),
        ("Por favor, edite este arquivo, preenchendo o ", "white"),
        ("MODEL", "cyan"),
        (" e a ", "white"),
        ("CONTEXT_LENGTH", "cyan"),
        (" para o modelo Ollama que você irá usar.\n\nApós editar, execute o programa novamente.", "white")
      ),
      title="[yellow]Ação Necessária[/yellow]",
      border_style="yellow"
    )
    console.print(action_panel)
    return False # Encerra a execução para o usuário preencher o arquivo

  load_dotenv(dotenv_path=".env", encoding="utf-8", override=True)
  
  missing_vars = []
  # Verifica se a variável existe e não é o valor placeholder
  model = os.getenv("MODEL")
  if not model or "ollama/<<NOME-DO-MODELO>>" in model:
    missing_vars.append("MODEL")

  context_length = os.getenv("CONTEXT_LENGTH")
  if not context_length or "<<JANELA-DE-CONTEXTO>>" in context_length or not context_length.isdigit():
    missing_vars.append("CONTEXT_LENGTH")

  if missing_vars:
    vars_str = ", ".join([f"[bold yellow]{var}[/bold yellow]" for var in missing_vars])
    message = Text.assemble(
      "O arquivo .env foi encontrado, mas as seguintes variáveis não foram preenchidas corretamente: ",
      Text.from_markup(vars_str),
      "\n\nPor favor, corrija o arquivo .env."
    )

    error_panel = Panel(
      message,
      title="[bold red]Erro de Configuração[/bold red]",
      border_style="red"
    )
    console.print(error_panel)
    return False
  
  console.print(":white_check_mark: [bold green]Arquivo .env carregado com sucesso.[/bold green]")
  return True

if __name__ == "__main__":
  if not check_and_load_dotenv():
    raise SystemExit(1)
  
  if not check_ollama_setup(os.getenv("MODEL")):
    raise SystemExit(1)