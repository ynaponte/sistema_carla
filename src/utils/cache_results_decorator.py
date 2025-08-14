import asyncio
import functools
import json
import os
from typing import Optional, Any, Callable, Literal

# Nome da pasta de cache fixo
NOME_PASTA_CACHE = "execution_cache"

def _try_load_from_cache(cache_file_path, func_name, context_str=""):
    """
    Tenta carregar o resultado do cache.
    Retorna (resultado_cacheado, True) se bem-sucedido, senão (None, False).
    """
    if os.path.exists(cache_file_path):
        try:
            with open(cache_file_path, 'r', encoding='utf-8') as f:
                cached_result = json.load(f)
            print(f"INFO: Resultado para '{func_name}' {context_str}carregado do cache: {cache_file_path}")
            return cached_result, True
        except (json.JSONDecodeError, IOError) as e:
            print(f"AVISO: Erro ao ler cache de '{cache_file_path}' {context_str}: {e}. Reexecutando.")
    return None, False

def _try_save_to_cache(cache_file_path, result, func_name, context_str=""):
    """
    Tenta salvar o resultado no cache.
    Assume que o diretório de cache já foi verificado/criado.
    """
    try:
        with open(cache_file_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=4)
        # print(f"INFO: Resultado para '{func_name}' {context_str}salvo no cache: {cache_file_path}")
    except (TypeError, IOError) as e:
        # TypeError ocorre se 'result' não for serializável para JSON
        print(f"AVISO: Erro ao salvar resultado no cache para '{func_name}' {context_str}: {e}. Resultado não foi cacheado.")

def _update_state_if_needed(
    state_path: Optional[str], 
    action: Literal['set', 'append'], 
    args: tuple, 
    result: Any
):
    """Atualiza uma variável de estado na instância da classe, suportando caminhos aninhados."""
    if not state_path or not args:
        return

    instance = args[0]
    parts = state_path.split('.')
    obj_to_update = instance
    
    try:
        for part in parts[:-1]:
            obj_to_update = getattr(obj_to_update, part)
        
        final_attribute_name = parts[-1]
        if action == 'set':
            setattr(obj_to_update, final_attribute_name, result)
        elif action == 'append':
            target_object = getattr(obj_to_update, final_attribute_name)
            if isinstance(target_object, list):
                target_object.append(result)            
            else:
                print(f"AVISO: O atributo '{final_attribute_name}' em '{state_path}' não é uma lista. Não foi possível usar a ação 'append'.")
        else:
            print(f"AVISO: Ação de atualização de estado desconhecida: '{action}'. Use 'set' ou 'append'.")
    except AttributeError:
        # Se getattr falhar em qualquer ponto do caminho, significa que o caminho é inválido.
        # Isso é um erro de programação e deve ser reportado claramente.
        raise AttributeError(
            f"Ação '{action}' falhou: O caminho de estado '{state_path}' não foi encontrado. Verifique se o atributo foi inicializado "
            "e se o nome está correto."
        )
    except Exception as e:
        print(f"AVISO: Erro inesperado ao tentar atualizar o estado '{state_path}': {e}")

def cache_execution(
    *, 
    state_variable_to_update: Optional[str] = None, 
    state_update_action: Literal['set', 'append'] = 'set'
) -> Callable:
    """
    Decorador para cachear o resultado de um método. DEVE ser chamado com parênteses.
    Ex: @cache_execution() ou @cache_execution(state_variable_to_update="...")

    - Suporta métodos síncronos e assíncronos, preservando a forma de chamada.
    - O nome do arquivo de cache é APENAS o nome do método.
    - NÃO é sensível aos argumentos do método para a chave do cache.
    - Opcionalmente, atualiza uma variável de estado na instância da classe.

    Args:
        state_variable_to_update (Optional[str]): O nome (ou caminho com pontos)
            da variável na instância (`self`) a ser atualizada.
    """
    def decorator(func_to_wrap: Callable) -> Callable:
        func_name = func_to_wrap.__name__
        cache_file_path = os.path.join(NOME_PASTA_CACHE, f"{func_name}.json")

        if asyncio.iscoroutinefunction(func_to_wrap):
            @functools.wraps(func_to_wrap)
            async def async_wrapper(*args, **kwargs):
                os.makedirs(NOME_PASTA_CACHE, exist_ok=True)
                final_result, loaded = _try_load_from_cache(cache_file_path, func_name, "(async) ")
                
                if not loaded:
                    final_result = await func_to_wrap(*args, **kwargs)
                    _try_save_to_cache(cache_file_path, final_result, func_name, "(async) ")
                
                _update_state_if_needed(state_variable_to_update, state_update_action, args, final_result)
                return final_result
            return async_wrapper
        else:
            @functools.wraps(func_to_wrap)
            def sync_wrapper(*args, **kwargs):
                os.makedirs(NOME_PASTA_CACHE, exist_ok=True)
                final_result, loaded = _try_load_from_cache(cache_file_path, func_name, "(sync) ")

                if not loaded:
                    final_result = func_to_wrap(*args, **kwargs)
                    _try_save_to_cache(cache_file_path, final_result, func_name, "(sync) ")

                _update_state_if_needed(state_variable_to_update, state_update_action, args, final_result)
                return final_result
            return sync_wrapper
    return decorator

def cache_execution(
    *, 
    state_variable_to_update: Optional[str] = None, 
    state_update_action: Literal['set', 'append'] = 'set'
) -> Callable:
    """
    Decorador para cachear o resultado de um método. DEVE ser chamado com parênteses.
    Ex: @cache_execution() ou @cache_execution(state_variable_to_update="...")

    - Suporta métodos síncronos e assíncronos, preservando a forma de chamada.
    - O nome do arquivo de cache é APENAS o nome do método.
    - NÃO é sensível aos argumentos do método para a chave do cache.
    - Opcionalmente, atualiza uma variável de estado na instância da classe.

    Args:
        state_variable_to_update (Optional[str]): O nome (ou caminho com pontos)
            da variável na instância (`self`) a ser atualizada.
    """
    def decorator(func: Callable) -> Callable:
        func_name = func.__name__
        cache_file_path = os.path.join(NOME_PASTA_CACHE, f"{func_name}.json")

        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                os.makedirs(NOME_PASTA_CACHE, exist_ok=True)
                final_result, loaded = _try_load_from_cache(cache_file_path, func_name, "(async) ")
                
                if not loaded:
                    final_result = await func(*args, **kwargs)
                    _try_save_to_cache(cache_file_path, final_result, func_name, "(async) ")
                
                _update_state_if_needed(state_variable_to_update, state_update_action, args, final_result)
                return final_result
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                os.makedirs(NOME_PASTA_CACHE, exist_ok=True)
                final_result, loaded = _try_load_from_cache(cache_file_path, func_name, "(sync) ")

                if not loaded:
                    final_result = func(*args, **kwargs)
                    _try_save_to_cache(cache_file_path, final_result, func_name, "(sync) ")

                _update_state_if_needed(state_variable_to_update, state_update_action, args, final_result)
                return final_result
            return sync_wrapper
    
    return decorator