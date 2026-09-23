import os
import glob
import yaml
from typing import Any, Dict, Optional, List
from jinja2 import Template

class PromptRegistry:
    """Centralized SemVer Prompt Management Registry with Jinja2 Templating."""

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        self.base_dir = base_dir
        self._cache: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.reload()

    def reload(self):
        """Scans and caches all prompt YAML files in the prompts directory."""
        self._cache.clear()
        yaml_files = glob.glob(os.path.join(self.base_dir, "**", "*.yaml"), recursive=True)
        
        for file_path in yaml_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if not isinstance(data, dict) or "metadata" not in data or "template" not in data:
                    continue
                
                meta = data.get("metadata", {})
                category = meta.get("category", os.path.basename(os.path.dirname(file_path)))
                name = meta.get("name", os.path.splitext(os.path.basename(file_path))[0])
                version = str(meta.get("version", "1.0.0")).lstrip("v")
                
                if category not in self._cache:
                    self._cache[category] = {}
                if name not in self._cache[category]:
                    self._cache[category][name] = {}
                
                self._cache[category][name][version] = {
                    "metadata": meta,
                    "template": data["template"],
                    "file_path": file_path,
                }
            except Exception as e:
                print(f"[PromptRegistry Warning] Failed to load {file_path}: {e}")

    def get_prompt(
        self,
        category: str,
        name: Optional[str] = None,
        version: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Retrieves and renders a prompt template.

        Args:
            category: Category folder name (e.g., 'system_instructions', 'image_gen', 'video_gen')
            name: Specific prompt name (defaults to category or first matching name)
            version: Exact SemVer string (e.g. '1.0.0'). If None or 'latest', uses highest version.
            **kwargs: Dynamic variables passed to Jinja2 template renderer.

        Returns:
            Rendered prompt string.
        """
        if category not in self._cache:
            raise KeyError(f"Prompt category '{category}' not found in registry. Available: {list(self._cache.keys())}")
        
        cat_prompts = self._cache[category]
        if name is None:
            name = list(cat_prompts.keys())[0] if cat_prompts else category
        
        if name not in cat_prompts:
            raise KeyError(f"Prompt name '{name}' not found under category '{category}'. Available: {list(cat_prompts.keys())}")
        
        versions = cat_prompts[name]
        if not versions:
            raise ValueError(f"No prompt versions found for '{category}/{name}'.")

        target_version = version
        if target_version is None or target_version == "latest":
            # Sort version strings semantically
            sorted_versions = sorted(versions.keys(), key=lambda v: [int(x) if x.isdigit() else x for x in v.split(".")])
            target_version = sorted_versions[-1]
        else:
            target_version = str(target_version).lstrip("v")
            if target_version not in versions:
                raise KeyError(f"Version '{version}' not found for '{category}/{name}'. Available versions: {list(versions.keys())}")

        entry = versions[target_version]
        raw_template = entry["template"]
        template = Template(raw_template)
        return template.render(**kwargs).strip()

    def get_metadata(
        self,
        category: str,
        name: Optional[str] = None,
        version: Optional[str] = None
    ) -> Dict[str, Any]:
        """Returns metadata for a prompt."""
        if category not in self._cache:
            return {}
        cat_prompts = self._cache[category]
        if name is None:
            name = list(cat_prompts.keys())[0] if cat_prompts else category
        if name not in cat_prompts:
            return {}
        versions = cat_prompts[name]
        if version is None or version == "latest":
            sorted_versions = sorted(versions.keys(), key=lambda v: [int(x) if x.isdigit() else x for x in v.split(".")])
            version = sorted_versions[-1]
        else:
            version = str(version).lstrip("v")
        return versions.get(version, {}).get("metadata", {})

    def list_prompts(self) -> Dict[str, List[Dict[str, Any]]]:
        """Lists all registered prompts with their metadata and available versions."""
        summary = {}
        for category, cat_dict in self._cache.items():
            summary[category] = []
            for name, versions in cat_dict.items():
                v_list = list(versions.keys())
                latest_v = sorted(v_list, key=lambda v: [int(x) if x.isdigit() else x for x in v.split(".")])[-1]
                meta = versions[latest_v]["metadata"]
                summary[category].append({
                    "name": name,
                    "latest_version": latest_v,
                    "available_versions": v_list,
                    "description": meta.get("description", ""),
                    "author": meta.get("author", "")
                })
        return summary


# Global singleton instance
prompt_registry = PromptRegistry()
