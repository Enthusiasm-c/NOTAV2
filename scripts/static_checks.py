#!/usr/bin/env python3
"""
Статический анализатор кода для поиска проблем после отказа от SQL.
"""
import ast
import pathlib
import sys
from typing import Set, List, Tuple, Union

ROOT = pathlib.Path(__file__).resolve().parents[1]

def is_coroutine(node: Union[ast.Attribute, ast.Name], async_defs: Set[str]) -> bool:
    """Проверяет, является ли узел корутиной."""
    return isinstance(node, ast.Name) and node.id in async_defs

def check_await_misuse(path: pathlib.Path, tree: ast.AST, async_funcs: Set[str]) -> List[str]:
    """Ищет неправильное использование await."""
    errors = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Await):
            target = node.value
            if not is_coroutine(target, async_funcs):
                errors.append(f"{path}:{node.lineno} — await on non-coroutine: {ast.unparse(target)}")
    return errors

def check_sql_imports(path: pathlib.Path, tree: ast.AST) -> List[str]:
    """Ищет импорты SQL-зависимостей."""
    errors = []
    sql_modules = {
        'sqlalchemy', 'asyncpg', 'alembic',
        'app.models', 'app.database'
    }
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                if any(name.name.startswith(m) for m in sql_modules):
                    errors.append(f"{path}:{node.lineno} — forbidden SQL import: {name.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ''
            if any(module.startswith(m) for m in sql_modules):
                errors.append(f"{path}:{node.lineno} — forbidden SQL import: {module}")
    return errors

def check_global_refs(path: pathlib.Path, tree: ast.AST) -> List[str]:
    """Проверяет корректность использования глобальных переменных."""
    errors = []
    globals_to_check = {'PRODUCTS', 'SUPPLIERS'}
    
    class GlobalChecker(ast.NodeVisitor):
        def __init__(self):
            self.defined_globals = set()
            self.used_globals = set()
            
        def visit_Global(self, node: ast.Global):
            self.defined_globals.update(name for name in node.names if name in globals_to_check)
            
        def visit_Name(self, node: ast.Name):
            if isinstance(node.ctx, ast.Load) and node.id in globals_to_check:
                self.used_globals.add(node.id)
    
    checker = GlobalChecker()
    checker.visit(tree)
    
    for name in checker.used_globals - checker.defined_globals:
        errors.append(f"{path} — global variable {name} used but not declared")
    
    return errors

def main() -> None:
    """Основная функция проверки."""
    all_errors: List[Tuple[str, List[str]]] = []
    
    for path in ROOT.rglob("*.py"):
        # Пропускаем виртуальное окружение и .git
        if any(p in {".venv", "venv", ".git"} for p in path.parts):
            continue
            
        try:
            src = path.read_text()
            tree = ast.parse(src, filename=str(path))
            
            # Собираем все async функции
            async_funcs = {
                n.name for n in ast.walk(tree) 
                if isinstance(n, ast.AsyncFunctionDef)
            }
            
            # Проверяем await
            await_errors = check_await_misuse(path, tree, async_funcs)
            if await_errors:
                all_errors.append(("await-misuse", await_errors))
            
            # Проверяем SQL импорты
            sql_errors = check_sql_imports(path, tree)
            if sql_errors:
                all_errors.append(("sql-imports", sql_errors))
            
            # Проверяем глобальные переменные
            global_errors = check_global_refs(path, tree)
            if global_errors:
                all_errors.append(("global-refs", global_errors))
                
        except Exception as e:
            print(f"Error processing {path}: {e}", file=sys.stderr)
    
    if all_errors:
        for category, errors in all_errors:
            print(f"\n⚠️  {category}:")
            print("\n".join(f"  {e}" for e in errors))
        sys.exit(1)
    else:
        print("✅ All checks passed")
        sys.exit(0)

if __name__ == "__main__":
    main() 