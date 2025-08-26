import json
import os
import pathlib
import typer
from typing import Dict, List
from rich.console import Console
from rich.panel import Panel

# Constantes e inicializações
console = Console()
# Passo 2: Atualizar o nome do arquivo de configuração
CONFIG_FILE = "carla.json"
REQUIRED_KEYS = ["report", "references", "results", "database"]

# --- Funções Auxiliares de Manipulação do CFG ---

def load_config() -> dict:
  """Carrega o arquivo de configuração .cfg e retorna a seção [paths] como um dicionário."""
  if not os.path.exists(CONFIG_FILE): return {}
  try:
      with open(CONFIG_FILE, 'r', encoding="utf-8") as f:
          return json.load(f)
  except (json.JSONDecodeError, FileNotFoundError):
      return {}

def save_config(config_data: Dict[str, List[str] | str]):
  """Salva o dicionário de configuração em um arquivo JSON."""
  with open(CONFIG_FILE, 'w', encoding="utf-8") as f:
    json.dump(config_data, f, indent=4)
  console.print(f":floppy_disk: [green]Configuração salva em '{CONFIG_FILE}'[/green]")

def resolve_path(path_str: str) -> pathlib.Path:
    """Converte um caminho em string para um objeto Path absoluto e resolvido."""
    # pathlib.Path lida com '~' para a pasta home.
    # .expanduser() resolve o '~'.
    # .resolve() cria o caminho absoluto completo.
    return pathlib.Path(path_str).expanduser().resolve()

def verify_path(path: str, key_name: str) -> bool:
  """Verifica se um caminho é válido, com regra especial para a base de dados."""
  
  # Resolução do path para formato absoluto. Também verifica se o caminho é válido.
  try:
    absolute_path = resolve_path(path)

  except Exception:
    console.print(f"[red]  -> Erro:[/red] O caminho '[cyan]{path}[/cyan]' para '[bold]{key_name}[/bold]' é inválido.")
    return False
  
  # Verifica se o caminho se é um diretório ou, o caso especial, de não ser diretório e não existir (i.e não é um arquivo)
  # mas a chave ser 'database'.
  if absolute_path.is_dir() or key_name == "database" and not absolute_path.exists():      
      return True
    
  # Informa ao usuário que o caminho especificado é inválido  
  console.print(f"[red]  -> Erro:[/red] O caminho '[cyan]{path}[/cyan]' para '[bold]{key_name}[/bold]' é inválido.")
  return False

# --- Assistente de Configuração Inicial ---

def run_setup_wizard() -> dict:
  """
  Executa o assistente de configuração inicial.
  """
  console.print(Panel("Assistente de Configuração do Sistema CARLA", title="[yellow]Configuração Necessária[/yellow]", border_style="yellow"))
  console.print(f"Vamos definir as pastas de trabalho para o seu projeto (caminho absoluto ou relativo):")
  config = {}

  for required_key in REQUIRED_KEYS:
    default_path_obj = pathlib.Path('.') / required_key
    default_path_str = str(default_path_obj.resolve())
    prompt_text = f"Especifique o caminho para '{required_key}' "
    
    # Entrada para casos especiais: report e database
    if required_key == "report" or required_key == "database":
      prompt_text += "(apenas um caminho permitido)"
      user_input = typer.prompt(prompt_text, default=default_path_str)

      if ',' in user_input:
        console.print(f"\n[bold red]Erro: Apenas um caminho é permitido para '{required_key}'. Usando o primeiro caminho informado.[/bold red]")
        user_input = user_input.split(',')[0].strip()

      user_input = [user_input] if required_key == 'report' else user_input

    # Entrada para demais casos
    else:
      prompt_text += "(se mais de um, separe por vírgula)"
      user_input = typer.prompt(prompt_text, default=default_path_str)
      user_input = [path.strip() for path in user_input.split(',')]

    config[required_key] = user_input

  return config

# --- Assistente de Validação de Entrada ---

def run_ratification_wizard(config: dict, invalid_keys: List[str]) -> dict:
  """
  Executa o assistente de validação de entrada.
  """
  console.print(
    Panel(
      "Algumas configurações estão inválidas. Vamos corrigi-las.", 
      title="[yellow]Assistente de Correção[/yellow]", 
      border_style="yellow"
    )
  )
  corrected_config = config.copy()

  # Inicia a correção chave a chave
  for key in invalid_keys:
    prompt_text = f"Por favor, forneça um novo caminho para '{key}' "
    is_report = key == "report"
    is_database = key == "database"
    prompt_text += "(apenas um caminho permitido)" if is_report or is_database else "(se mais de um, separe por vírgula)"
    all_paths_valid = False
    
    # Verifica se todos os caminhos informados são válidos. Caso não, pede para o usuário fornece-lo novamente
    while not all_paths_valid:
      user_input = typer.prompt(prompt_text)
      new_paths = [path.strip() for path in user_input.split(',')]

      # Verifica se o usuário passou mais de um caminho para a base de dados ou para o dir do relatório
      if (is_report or is_database) and len(new_paths) > 1: 
        console.print(f"[bold red]Erro: Apenas um caminho é permitido para '{key}'. Tente novamente.[/bold red]")
        continue
      
      # Verificação de caminho
      for path in new_paths:
        all_paths_valid = verify_path(path, key)
        if not all_paths_valid: 
          console.print("[yellow]O caminho fornecido ainda é inválido. Por favor, tente novamente.[/yellow]")
          break
        
        # "Altera" o formato de lista para string, no caso da chave ser 'database'.
        corrected_config[key] = new_paths if not is_database else new_paths[0]
  
  return corrected_config

# --- Função Principal de Validação ---

def get_and_validate_project_config() -> dict | None:
  """
  Valida a configuração do projeto. A lógica interna não muda, pois opera
  em um dicionário Python padrão que é abstraído pelas funções load/save.
  """
  console.print("Verificando configuração do projeto...")
  config = load_config()
  config_was_valid = True

  if not config:
    console.print(
      f"[yellow]O arquivo de configuração '{CONFIG_FILE}' não foi encontrado ou está vazio.[/yellow]\n"
      "Iniciando o assistente de configuração inicial...\n"
    )
    config_was_valid = False
    config = run_setup_wizard()
  
  invalid_keys = []
  
  # Busca por chaves invalidas
  for key in REQUIRED_KEYS:
    if key not in config.keys():
      config_was_valid = False
      invalid_keys.append(key)
      continue
    
    value = config[key]
    paths_to_check = value if isinstance(value, list) else [value]

    for path in paths_to_check:
      if not verify_path(path, key):
        config_was_valid = False
        invalid_keys.append(key)
  
  # Corrige as chaves inválidas
  if invalid_keys:
    config_was_valid = False
    config = run_ratification_wizard(config, invalid_keys)
  
  if not config_was_valid:
    save_config(config)
  
  return config

if __name__ == "__main__":
  get_and_validate_project_config()
  