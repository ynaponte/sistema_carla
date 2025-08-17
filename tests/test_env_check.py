import os
import sys
import pathlib
import pytest
from rich.console import Console

# Ajusta o sys.path para importar o módulo sob teste
THIS_DIR = pathlib.Path(__file__).parent.resolve()
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from src.cli import env_check  # noqa: E402


# --------------------------
# Fixtures & Utilitários
# --------------------------

@pytest.fixture(autouse=True)
def isolated_cwd(tmp_path):
    """
    Executa cada teste num diretório temporário,
    evitando sobrescrever arquivos reais (.env).
    """
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        yield tmp_path
    finally:
        os.chdir(old_cwd)


class CaptureConsole(Console):
    """Console Rich que captura a saída como texto renderizado."""
    def __init__(self):
        super().__init__(record=True)
    def get_text(self):
        return self.export_text()


# --------------------------
# Testes para check_and_load_dotenv
# --------------------------

def test_creates_env_if_missing(monkeypatch, tmp_path):
    cap_console = CaptureConsole()
    monkeypatch.setattr(env_check, "console", cap_console)
    monkeypatch.delenv("MODEL", raising=False)
    monkeypatch.delenv("CONTEXT_LENGTH", raising=False)

    # .env não existe inicialmente
    assert not os.path.exists(".env")

    result = env_check.check_and_load_dotenv()
    assert result is False  # deve encerrar pedindo edição

    # O arquivo .env deve ter sido criado com placeholders
    env_text = pathlib.Path(".env").read_text(encoding="utf-8")
    assert "MODEL=" in env_text
    assert "<<NOME-DO-MODELO>>" in env_text
    assert "CONTEXT_LENGTH=" in env_text
    assert "<<JANELA-DE-CONTEXTO>>" in env_text

    out = cap_console.get_text()
    assert "Ação Necessária" in out


def test_env_with_missing_vars(monkeypatch):
    cap_console = CaptureConsole()
    monkeypatch.setattr(env_check, "console", cap_console)
    monkeypatch.delenv("MODEL", raising=False)
    monkeypatch.delenv("CONTEXT_LENGTH", raising=False)

    # Criar .env com placeholders ainda presentes
    with open(".env", "w", encoding="utf-8") as f:
        f.write('MODEL=ollama/<<NOME-DO-MODELO>>\n')
        f.write('CONTEXT_LENGTH=<<JANELA-DE-CONTEXTO>>\n')

    result = env_check.check_and_load_dotenv()
    assert result is False

    out = cap_console.get_text()
    assert "Erro de Configuração" in out
    assert "MODEL" in out
    assert "CONTEXT_LENGTH" in out

def test_env_with_non_numeric_context_length(monkeypatch):
    cap_console = CaptureConsole()
    monkeypatch.setattr(env_check, "console", cap_console)
    monkeypatch.delenv("MODEL", raising=False)
    monkeypatch.delenv("CONTEXT_LENGTH", raising=False)

    with open(".env", "w", encoding="utf-8") as f:
        f.write('MODEL=ollama/mistral\n')
        f.write('CONTEXT_LENGTH=not_a_number\n')

    result = env_check.check_and_load_dotenv()
    assert result is False

    out = cap_console.get_text()
    assert "Erro de Configuração" in out
    assert "CONTEXT_LENGTH" in out
    assert "MODEL" not in out


def test_env_valid(monkeypatch):
    cap_console = CaptureConsole()
    monkeypatch.setattr(env_check, "console", cap_console)
    monkeypatch.delenv("MODEL", raising=False)
    monkeypatch.delenv("CONTEXT_LENGTH", raising=False)

    # Criar .env válido
    with open(".env", "w", encoding="utf-8") as f:
        f.write('MODEL=ollama/mistral\n')
        f.write('CONTEXT_LENGTH=4096\n')

    result = env_check.check_and_load_dotenv()
    assert result is True

    out = cap_console.get_text()
    assert "carregado com sucesso" in out
    assert "Erro de Configuração" not in out


# --------------------------
# Testes para check_ollama_setup
# --------------------------

class DummyClientOK:
    """Cliente ollama que retorna modelos simulados."""
    def list(self):
        return {"models": [{"model": "mistral"}, {"model": "gemma"}]}


class DummyClientFail:
    """Cliente ollama que lança erro de conexão."""
    def list(self):
        raise RuntimeError("Falha de conexão")


def test_check_ollama_service_unavailable(monkeypatch):
    cap_console = CaptureConsole()
    monkeypatch.setattr(env_check, "console", cap_console)
    monkeypatch.setattr(env_check.ollama, "Client", lambda: DummyClientFail())

    result = env_check.check_ollama_setup("ollama/mistral")
    assert result is False

    out = cap_console.get_text()
    assert "Ollama Inacessível" in out
    assert "Falha de conexão" in out


def test_check_ollama_model_not_found(monkeypatch):
    cap_console = CaptureConsole()
    monkeypatch.setattr(env_check, "console", cap_console)
    monkeypatch.setattr(env_check.ollama, "Client", lambda: DummyClientOK())

    result = env_check.check_ollama_setup("ollama/not_installed")
    assert result is False

    out = cap_console.get_text()
    assert "Modelo Não Encontrado" in out
    assert "not_installed" in out


def test_check_ollama_model_found(monkeypatch):
    cap_console = CaptureConsole()
    monkeypatch.setattr(env_check, "console", cap_console)
    monkeypatch.setattr(env_check.ollama, "Client", lambda: DummyClientOK())

    result = env_check.check_ollama_setup("ollama/mistral")
    assert result is True

    out = cap_console.get_text()
    assert "Modelo 'mistral' encontrado" in out
