# test_config_check.py
import os
import sys
import json
import pathlib
from pathlib import Path

import pytest

# --- Import do módulo sob teste (assume que o teste está no mesmo diretório do config_check.py)
THIS_DIR = pathlib.Path(__file__).parent.resolve()
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))
from src.cli import config_check  # noqa: E402


# --------------------------
# Fixtures & Test Utilities
# --------------------------

@pytest.fixture(autouse=True)
def isolated_cwd(tmp_path):
    """
    Executa cada teste num diretório temporário isolado.
    Garante que o carla.json usado é local (config_check usa caminho relativo).
    """
    old = os.getcwd()
    os.chdir(tmp_path)
    try:
        yield tmp_path
    finally:
        os.chdir(old)


class PromptSequencer:
    """Alimenta respostas para chamadas sequenciais de typer.prompt."""
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def __call__(self, text, default=None):
        self.calls.append((text, default))
        if self.answers:
            return self.answers.pop(0)
        # Se acabarem as respostas, usa default se existir; senão falha para expor inconsistência.
        if default is not None:
            return default
        raise AssertionError(f"Sem respostas para o prompt: {text!r}")


class FakeConsole:
    """Espião simples para config_check.console.print."""
    def __init__(self):
        self.messages = []

    def print(self, *args, **kwargs):
        self.messages.append((args, kwargs))


def write_json(data):
    with open(config_check.CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def read_json():
    if not Path(config_check.CONFIG_FILE).exists():
        return None
    with open(config_check.CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# --------------------------
# Testes unitários: utilitários
# --------------------------

def test_load_config_no_file_returns_empty():
    assert not Path(config_check.CONFIG_FILE).exists()
    assert config_check.load_config() == {}


def test_load_config_invalid_json_returns_empty():
    Path(config_check.CONFIG_FILE).write_text("{ invalid json", encoding="utf-8")
    assert config_check.load_config() == {}


def test_save_config_writes_json_and_prints(monkeypatch):
    fake = FakeConsole()
    monkeypatch.setattr(config_check, "console", fake)
    data = {"report": ["/tmp/rep"], "references": ["/tmp/ref"], "results": ["/tmp/res"], "database": "/tmp/db"}
    config_check.save_config(data)
    assert Path(config_check.CONFIG_FILE).exists()
    assert read_json() == data
    # houve um print de confirmação
    assert any(":floppy_disk:" in (args[0] if args else "") for args, _ in fake.messages)


def test_resolve_path_returns_absolute_and_expands_home(monkeypatch, tmp_path):
    # relativo -> absoluto
    p = config_check.resolve_path(".")

    assert isinstance(p, Path)
    assert p.is_absolute()

    # "~" deve expandir para home
    home_resolved = config_check.resolve_path("~")
    assert str(home_resolved).startswith(str(Path.home()))


# --------------------------
# Testes unitários: verify_path
# --------------------------

def test_verify_path_report_requires_existing_dir(tmp_path, monkeypatch):
    # diretório existente -> True
    d = tmp_path / "report_dir"; d.mkdir()
    assert config_check.verify_path(str(d), "report") is True

    # inexistente -> False
    assert config_check.verify_path(str(tmp_path / "does_not_exist"), "report") is False

    # arquivo -> False
    f = tmp_path / "file.txt"; f.write_text("x")
    assert config_check.verify_path(str(f), "report") is False


def test_verify_path_database_rules(tmp_path):
    # database inexistente -> True (será criado pelo sistema)
    db_future = tmp_path / "db_will_be_created"
    assert not db_future.exists()
    assert config_check.verify_path(str(db_future), "database") is True

    # database diretório existente -> True
    db_dir = tmp_path / "db_dir"; db_dir.mkdir()
    assert config_check.verify_path(str(db_dir), "database") is True

    # database aponta para arquivo -> False
    db_file = tmp_path / "db_file.sqlite"
    db_file.write_text("not a dir")
    assert config_check.verify_path(str(db_file), "database") is False


def test_verify_path_invalid_format_handled(monkeypatch):
    # Simula formato inválido forçando resolve_path a lançar exceção (independente de SO)
    def boom(_):
        raise ValueError("invalid path")
    monkeypatch.setattr(config_check, "resolve_path", boom)

    assert config_check.verify_path(":::???", "report") is False
    assert config_check.verify_path(":::???", "database") is False


# --------------------------
# Testes: run_setup_wizard
# --------------------------

def test_run_setup_wizard_types_and_single_path_rules(monkeypatch, tmp_path):
    """
    - report e database: só 1 caminho permitido; se vier com vírgulas, usa o primeiro.
    - references/results: lista a partir de vírgulas com trim.
    """
    fake = FakeConsole()
    monkeypatch.setattr(config_check, "console", fake)

    report_in = f"{tmp_path}/report_a, {tmp_path}/report_b"
    refs_in = f"{tmp_path}/r1 , {tmp_path}/r2"
    results_in = f"{tmp_path}/res1"
    db_in = f"{tmp_path}/db_a, {tmp_path}/db_b"

    prompts = PromptSequencer([report_in, refs_in, results_in, db_in])
    monkeypatch.setattr(config_check.typer, "prompt", prompts)

    cfg = config_check.run_setup_wizard()

    # Tipos
    assert isinstance(cfg["report"], list) and len(cfg["report"]) == 1
    assert isinstance(cfg["references"], list) and cfg["references"] == [f"{tmp_path}/r1", f"{tmp_path}/r2"]
    assert isinstance(cfg["results"], list) and cfg["results"] == [f"{tmp_path}/res1"]
    assert isinstance(cfg["database"], str)

    # Poda de múltiplos: só primeiro para report & database
    assert cfg["report"][0] == f"{tmp_path}/report_a"
    assert cfg["database"] == f"{tmp_path}/db_a"

    # Mensagens de erro de múltiplos para chaves single
    found_report_warning = any("Apenas um caminho é permitido para 'report'" in " ".join(map(str, args)) for args, _ in fake.messages)
    found_db_warning = any("Apenas um caminho é permitido para 'database'" in " ".join(map(str, args)) for args, _ in fake.messages)
    assert found_report_warning and found_db_warning


# --------------------------
# Testes: run_ratification_wizard
# --------------------------

def test_run_ratification_wizard_reprompts_until_valid(monkeypatch, tmp_path):
    """
    - report: usuário passa múltiplos -> rejeita e re-pede; depois fornece diretório válido.
    - database: usuário passa arquivo -> rejeita; depois fornece diretório inexistente -> aceita.
    - references: passa 2 caminhos, sendo 1 inexistente -> rejeita; depois 2 existentes -> aceita.
    """
    # Estado inicial (valores inválidos em algumas chaves)
    bad_db_file = tmp_path / "db.sqlite"; bad_db_file.write_text("x")
    config = {
        "report": ["bad_report"],           # inexistente
        "references": ["bad_r1", "bad_r2"], # inexistentes
        "results": [str((tmp_path / "res_ok").mkdir() or (tmp_path / "res_ok"))],
        "database": str(bad_db_file),       # arquivo (inválido)
    }
    invalid_keys = ["report", "database", "references"]

    # Prepara diretórios válidos que serão usados nas correções
    rep_ok = tmp_path / "report_ok"; rep_ok.mkdir()
    r1 = tmp_path / "r1"; r1.mkdir()
    r2 = tmp_path / "r2"; r2.mkdir()
    # Para database, não criaremos: inexistente é aceito
    db_new = tmp_path / "db_new"

    # Sequência de respostas:
    # - report: primeiro "rep1,rep2" (múltiplos -> rejeita), depois "report_ok" (aceita)
    # - database: primeiro arquivo (rejeita), depois caminho inexistente (aceita)
    # - references: primeiro "r1, inexistente" (rejeita), depois "r1, r2" (aceita)
    answers = [
        f"{tmp_path}/rep1, {tmp_path}/rep2",
        str(rep_ok),
        str(bad_db_file),
        str(db_new),
        f"{r1}, {tmp_path}/nope",
        f"{r1}, {r2}",
    ]
    prompts = PromptSequencer(answers)
    monkeypatch.setattr(config_check.typer, "prompt", prompts)

    fake = FakeConsole()
    monkeypatch.setattr(config_check, "console", fake)

    corrected = config_check.run_ratification_wizard(config, invalid_keys)

    # Valores finais corrigidos
    assert corrected["report"] == [str(rep_ok)]
    assert corrected["database"] == str(db_new)  # string, não lista
    assert corrected["references"] == [str(r1), str(r2)]

    # Mensagens esperadas apareceram
    msgs = " ".join(" ".join(map(str, a)) for a, _ in fake.messages)
    assert "Apenas um caminho é permitido para 'report'" in msgs
    assert "O caminho fornecido ainda é inválido" in msgs


# --------------------------
# Testes: get_and_validate_project_config
# --------------------------

def test_get_and_validate_project_config_when_missing_file_runs_setup_and_saves(monkeypatch, tmp_path):
    # Cria diretórios válidos para as chaves que exigem existência
    report_dir = tmp_path / "report"; report_dir.mkdir()
    refs_dir = tmp_path / "refs"; refs_dir.mkdir()
    results_dir = tmp_path / "results"; results_dir.mkdir()
    db_future = tmp_path / "db_future"  # não precisa existir

    prompts = PromptSequencer([str(report_dir), str(refs_dir), str(results_dir), str(db_future)])
    monkeypatch.setattr(config_check.typer, "prompt", prompts)

    # Espião de console para não poluir saída
    monkeypatch.setattr(config_check, "console", FakeConsole())

    cfg = config_check.get_and_validate_project_config()

    assert Path(config_check.CONFIG_FILE).exists()
    saved = read_json()
    # Tipos e valores
    assert saved["report"] == [str(report_dir)]
    assert saved["references"] == [str(refs_dir)]
    assert saved["results"] == [str(results_dir)]
    assert saved["database"] == str(db_future)
    assert cfg == saved


def test_get_and_validate_project_config_with_valid_existing_config_does_not_resave(monkeypatch, tmp_path):
    report_dir = tmp_path / "report"; report_dir.mkdir()
    refs_dir = tmp_path / "refs"; refs_dir.mkdir()
    results_dir = tmp_path / "results"; results_dir.mkdir()
    db_dir = tmp_path / "db"; db_dir.mkdir()  # existente também é válido

    existing = {
        "report": [str(report_dir)],
        "references": [str(refs_dir)],
        "results": [str(results_dir)],
        "database": str(db_dir),
    }
    write_json(existing)

    # Se tentar salvar, falha o teste
    def fail_save(_):
        raise AssertionError("save_config não deveria ser chamado quando tudo está válido")
    monkeypatch.setattr(config_check, "save_config", fail_save)

    cfg = config_check.get_and_validate_project_config()
    assert cfg == existing  # inalterado


def test_get_and_validate_project_config_with_missing_and_invalid_keys_triggers_ratification(monkeypatch, tmp_path):
    # Config inicial com problemas:
    # - report aponta para inexistente
    # - references ausente
    # - results ok
    # - database aponta para arquivo (inválido)
    res_ok = tmp_path / "results"; res_ok.mkdir()
    db_file = tmp_path / "db.sqlite"; db_file.write_text("x")

    write_json({
        "report": [str(tmp_path / "no_report")],
        "results": [str(res_ok)],
        "database": str(db_file),
    })

    # Respostas para ratificação:
    rep_ok = tmp_path / "report_ok"; rep_ok.mkdir()
    refs1 = tmp_path / "refs1"; refs1.mkdir()
    refs2 = tmp_path / "refs2"; refs2.mkdir()
    db_new = tmp_path / "db_new"  # inexistente é ok

    # Ordem dos prompts segue a ordem de invalid_keys coletadas;
    # Para simplificar, usamos respostas que funcionem na primeira tentativa.
    prompts = PromptSequencer([
        str(rep_ok),                 # report
        f"{refs1}, {refs2}",         # references (lista)
        str(db_new),                 # database
    ])
    monkeypatch.setattr(config_check.typer, "prompt", prompts)
    monkeypatch.setattr(config_check, "console", FakeConsole())

    cfg = config_check.get_and_validate_project_config()

    # Deve ter salvo correções
    saved = read_json()
    assert saved["report"] == [str(rep_ok)]
    assert saved["references"] == [str(refs1), str(refs2)]
    assert saved["results"] == [str(res_ok)]
    assert saved["database"] == str(db_new)
    assert cfg == saved
