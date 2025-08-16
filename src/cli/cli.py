from src.article_writer.main import ArticleWriterFlow
from env_check import check_and_load_dotenv, check_ollama_setup

import typer
import os
import json
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
# --- Configurações e Constantes ---
console = Console()
CONFIG_FILE = "carla_config.json"
APP_VERSION = "v0.8.2"
AUTHOR_INFO = "Ynã Ponte, 2025"  # <-- ALTERE AQUI COM SEU NOME
app = typer.Typer(add_completion=False)

# O banner ASCII art
BANNER = r"""
 ██████╗ █████╗ ██████╗ ██╗      █████╗ 
 ██╔════╝██╔══██╗██╔══██╗██║     ██╔══██╗
 ██║     ███████║██████╔╝██║     ███████║
 ██║     ██╔══██║██╔══██╗██║     ██╔══██║
 ╚██████╗██║  ██║██║  ██║███████╗██║  ██║
  ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝ 
"""

SUBTITLE = "Sistema CARLA - Contextualized Assisted Authoring from Results and References by LLM Agents"

# --- Funções de Placeholder (Mantenha as suas) ---

def sua_logica_de_vetorizacao(docs_path: str, references_path: str, results_path: str, db_path: str):
    """Placeholder para sua função que cria a base de dados vetorial."""
    console.print(f"\n[bold green]Iniciando a vetorização...[/bold green]")
    console.print(f"Lendo documentos de: [cyan]{docs_path}[/cyan]")
    # === SEU CÓDIGO DE VETORIZAÇÃO ENTRA AQUI ===
    #os.makedirs(db_path, exist_ok=True)
    #with open(os.path.join(db_path, "vector_db.faiss"), "w", encoding="utf-8") as f:
    #    f.write("dummy vector db")
    console.print(f"\n[bold green]Base de dados vetorial criada com sucesso em: [cyan]{db_path}[/cyan] :tada:")

def iniciar_sistema_multi_agente(config: dict):
    """Placeholder para a função que inicia seu sistema de agentes."""
    console.print("\n[bold magenta]Iniciando o sistema multi-agente CARLA...[/bold magenta]")
    # === SEU CÓDIGO PRINCIPAL ENTRA AQUI ===
    #ArticleWriterFlow().kickoff()
    console.print("\n[bold blue]Sessão CARLA finalizada. Obrigado por usar![/bold blue]")

def run_setup_wizard():
    """Executa o assistente de configuração das pastas e do carla_config.json."""
    console.print(Panel("Configuração das pastas de trabalho", title="[yellow]Assistente de Configuração[/yellow]", border_style="yellow"))
    console.print("Vamos definir as pastas para organização dos seus arquivos.")

    docs_path = typer.prompt("Nome da pasta para os documentos principais", default="documentos")
    references_path = typer.prompt("Nome da pasta para as referências", default="referencias")
    results_path = typer.prompt("Nome da pasta para os resultados prévios", default="resultados")
    db_path = typer.prompt("Nome da pasta para a base de dados vetorial", default="vector_db")

    config = { "docs_path": docs_path, "references_path": references_path, "results_path": results_path, "db_path": db_path }
    
    for path in config.values():
        os.makedirs(path, exist_ok=True)
    
    with open(CONFIG_FILE, 'w', encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    
    console.print("\n:white_check_mark: [bold green]Pastas criadas e configuração salva![/bold green]")
    console.print("\n[bold cyan]Ação necessária:[/bold cyan]")
    console.print(f"1. Adicione seus arquivos nas pastas criadas (ex: '{docs_path}').")
    console.print("2. Execute `python cli.py` novamente para continuar.")

# --- Comando Principal da Aplicação ---

@app.command()
def main():
    """Inicia e gerencia o ciclo de vida completo do sistema CARLA."""
    styled_banner = Text(BANNER, style="bold blue", justify="center")
    console.print(Panel(styled_banner, border_style="blue", expand=False))
    
    console.print(Text(f"\n{SUBTITLE}\n", style="blue", justify="center"))
    console.print(Rule(style="blue"))
    console.print(f"Versão: [bold yellow]{APP_VERSION}[/bold yellow] | Autor: [bold yellow]{AUTHOR_INFO}[/bold yellow]")
    console.print(Rule(style="blue"))

    if not check_and_load_dotenv():
        raise typer.Exit(code=1)
    
    if not check_ollama_setup(os.getenv("MODEL")):
        raise typer.Exit(code=1)

    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding="utf-8") as f:
            config = json.load(f)
    else:
        run_setup_wizard()
        raise typer.Exit()

    db_path = config.get("db_path")
    if not os.path.exists(os.path.join(db_path, "vector_db.faiss")):
        console.print(Panel("A base de dados vetorial ainda não foi criada.", title="[yellow]Próximo Passo: Indexação[/yellow]", border_style="yellow"))
        
        paths_to_check = [config['docs_path'], config['references_path'], config['results_path']]
        files_found = any(os.path.exists(p) and os.listdir(p) for p in paths_to_check)

        if not files_found:
            console.print("[bold red]Erro:[/bold red] Nenhum documento encontrado nas pastas de origem. Adicione os arquivos e execute novamente.")
            raise typer.Exit(code=1)

        if typer.confirm("Documentos encontrados. Deseja iniciar a indexação agora?", default=True):
            sua_logica_de_vetorizacao(
                docs_path=config['docs_path'],
                references_path=config['references_path'],
                results_path=config['results_path'],
                db_path=config['db_path']
            )
            console.print("\n[bold green]Indexação concluída.[/bold green] Execute `python cli.py` novamente para iniciar o sistema.")
        else:
            console.print("Indexação cancelada. Execute o script novamente quando estiver pronto.")
        raise typer.Exit()

    console.print(Panel.fit("[bold green]Tudo pronto para começar![/bold green]"))
    if typer.confirm("Deseja iniciar o sistema multi-agente CARLA agora?", default=True):
        iniciar_sistema_multi_agente(config)
    else:
        console.print("Execução cancelada pelo usuário.")

if __name__ == "__main__":
    main()