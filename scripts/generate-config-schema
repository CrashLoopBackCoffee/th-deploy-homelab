#!/usr/bin/env python3

import dataclasses
import importlib
import json
import os
import pathlib
import sys
import tomllib
import typing as t


@dataclasses.dataclass
class ConfigModel:
    name: str
    root: str
    model: str


# Module cache to avoid repeated imports
_module_cache: dict[str, t.Any] = {}


def get_configs() -> list[ConfigModel]:
    data = tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))
    configs = data.get('tool', {}).get('config-models', {})
    return [ConfigModel(name=key, **value) for key, value in configs.items()]


def get_config_root_model(config: ConfigModel):
    cache_key = f'{config.root}:{config.model}'

    if cache_key in _module_cache:
        return _module_cache[cache_key]

    sys.path.append(config.root)
    module_name, class_name = config.model.rsplit(':', 1)
    module = importlib.import_module(module_name)
    model_class = getattr(module, class_name)

    # Cache the result
    _module_cache[cache_key] = model_class
    return model_class


def should_regenerate_schema(config: ConfigModel) -> bool:
    """Check if schema needs regeneration based on file timestamps."""
    schema_file = pathlib.Path(config.root) / '.config-schema.json'

    if not schema_file.exists():
        return True

    # Check if any Python files in the config directory are newer than schema
    config_dir = pathlib.Path(config.root)
    schema_mtime = schema_file.stat().st_mtime

    for py_file in config_dir.rglob('*.py'):
        if py_file.stat().st_mtime > schema_mtime:
            return True

    return False


def generate_json_schema(config: ConfigModel) -> tuple[str, bool]:
    """Generate JSON schema for a config. Returns (config_name, success)."""
    try:
        # Skip if schema is up to date
        if not should_regenerate_schema(config):
            return (config.name, True)

        # Discover root model class
        root_model_class = get_config_root_model(config)
        if not root_model_class:
            return (config.name, False)

        if hasattr(root_model_class, 'model_json_schema'):
            # Pydantic v2
            schema = json.dumps(root_model_class.model_json_schema())
        else:
            # Fallback to Pydantic v1
            schema = root_model_class.schema_json()

        schema_file = pathlib.Path(config.root) / '.config-schema.json'
        schema_file.write_text(schema, encoding='utf-8')

        return (config.name, True)
    except Exception as e:
        print(f'Error generating schema for {config.name}: {e}')
        return (config.name, False)


def collect_vscode_settings_updates(configs: list[ConfigModel]) -> dict[str, str]:
    """Collect all VSCode settings updates that need to be made."""
    updates = {}
    for config in configs:
        schema_file = pathlib.Path(config.root) / '.config-schema.json'
        if schema_file.exists():
            updates[str(schema_file)] = f'{config.root}/Pulumi.*.yaml'
    return updates


def update_vscode_settings(schema_updates: dict[str, str]):
    """Update VSCode settings with all schema mappings at once."""
    settings_file = pathlib.Path('.vscode/settings.json')

    if not settings_file.exists():
        # No VSCode settings file found, create one
        pathlib.Path('.vscode').mkdir(exist_ok=True)
        settings = {'yaml.schemas': schema_updates}
        settings_file.write_text(json.dumps(settings, indent=4), encoding='utf-8')
        return

    # Load existing settings
    settings = json.loads(settings_file.read_text(encoding='utf-8'))

    # Update schema settings
    if 'yaml.schemas' not in settings:
        settings['yaml.schemas'] = {}

    missing_schemas = []
    for schema_file, pattern in schema_updates.items():
        if schema_file not in settings['yaml.schemas']:
            missing_schemas.append((schema_file, pattern))
            settings['yaml.schemas'][schema_file] = pattern

    # Write back if there were updates
    if missing_schemas:
        settings_file.write_text(json.dumps(settings, indent=4), encoding='utf-8')

    # Print any schemas that were missing
    if missing_schemas:
        print('Added missing schema mappings to .vscode/settings.json:')
        for schema_file, pattern in missing_schemas:
            print(f'  "{schema_file}": "{pattern}"')


def main():
    if os.environ.get('PULUMI_CI_SYSTEM'):
        return

    configs = get_configs()

    # Process schemas sequentially to avoid event loop issues in threads with Pydantic v2
    successful_configs = []
    for config in configs:
        config_name, success = generate_json_schema(config)

        if success:
            print(f'✓ Generated JSON schema for {config_name}')
            successful_configs.append(config)
        else:
            print(f'✗ Failed to generate schema for {config_name}')

    # Batch update VSCode settings for all successful configs
    if successful_configs:
        schema_updates = collect_vscode_settings_updates(successful_configs)
        update_vscode_settings(schema_updates)

    # Clean up module cache to free memory
    _module_cache.clear()


if __name__ == '__main__':
    main()
