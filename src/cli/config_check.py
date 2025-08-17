import os
import configparser
import typer
from rich.console import Console
from rich.panel import Panel

# Constantes e inicializações
console = Console()
# Passo 2: Atualizar o nome do arquivo de configuração
CONFIG_FILE = "carla.cfg"
REQUIRED_KEYS = ["report_path", "references_path", "results_path", "vectorstore_path"]

# --- Funções Auxiliares de Manipulação do CFG ---

def load_config() -> dict:
  """Carrega o arquivo de configuração .cfg e retorna a seção [paths] como um dicionário."""
  config = configparser.ConfigParser()
  config.read(CONFIG_FILE, encoding="utf-8")
  
  # Verifica se a seção [paths] existe e a retorna como um dicionário.
  # Se não existir, retorna um dicionário vazio.
  if 'paths' in config:
      return dict(config['paths'])
  return {}

def save_config(config_data: dict):
  """Salva o dicionário de configuração na seção [paths] do arquivo .cfg."""
  config = configparser.ConfigParser()
  config['paths'] = config_data
  
  with open(CONFIG_FILE, 'w', encoding="utf-8") as configfile:
      config.write(configfile)
  console.print(f":floppy_disk: [green]Configuração salva em '{CONFIG_FILE}'[/green]")

# --- Assistente de Configuração Inicial ---

def run_setup_wizard() -> dict:
  """
  Executa o assistente de configuração inicial.
  """
  console.print(Panel("Assistente de Configuração do Sistema CARLA", title="[yellow]Configuração Necessária[/yellow]", border_style="yellow"))
  console.print("Vamos definir as pastas de trabalho para o seu projeto.")

  config = {
      "report_path": typer.prompt("Caminho para a pasta contendo o relatório", default="./report"),
      "references_path": typer.prompt("Caminho para a pasta de referências", default="./references"),
      "results_path": typer.prompt("Caminho para a pasta de resultados prévios", default="./results"),
      "db_path": typer.prompt("Caminho para a pasta da base de dados vetorial", default="./article_vectorstore")
  }
  
  console.print("\n[bold]Criando as pastas necessárias...[/bold]")
  for path in config.values():
      os.makedirs(path, exist_ok=True)
  
  save_config(config)
  return config

# --- Função Principal de Validação ---

def validate_project_config() -> dict | None:
  """
  Valida a configuração do projeto. A lógica interna não muda, pois opera
  em um dicionário Python padrão que é abstraído pelas funções load/save.
  """
  config = load_config()
  
  if not config:
    console.print(f"[yellow]O arquivo de configuração '{CONFIG_FILE}' não foi encontrado ou está vazio.[/yellow]")
    config = run_setup_wizard()
    console.print("\n[green]Configuração inicial concluída com sucesso![/green]")
    return config

  config_updated = False
  temp_config = config.copy()

  for key in REQUIRED_KEYS:
    if not temp_config.get(key):
      console.print(f"\n[yellow]A configuração para '[bold]{key}[/bold]' está faltando.[/yellow]")
      new_path = typer.prompt(f"Por favor, forneça o caminho para '{key}'")
      temp_config[key] = new_path
      config_updated = True

      path_to_check = temp_config[key]
      while not os.path.isdir(path_to_check):
        console.print(f"\n[bold red]Erro:[/bold red] O caminho '[cyan]{path_to_check}[/cyan]' para '[bold]{key}[/bold]' não é um diretório válido ou acessível.")
        
        try_create = typer.confirm(f"Deseja tentar criar o diretório '{path_to_check}' agora?")
        if try_create:
          os.makedirs(path_to_check, exist_ok=True)
          console.print(f"[green]Diretório '{path_to_check}' criado com sucesso![/green]")
        else:
          path_to_check = typer.prompt(f"Por favor, forneça um caminho alternativo e válido para '{key}'")
          temp_config[key] = path_to_check
          config_updated = True
  
  if config_updated:
      save_config(temp_config)
  
  return temp_config

if __name__ == "__main__":
  validate_project_config()
  