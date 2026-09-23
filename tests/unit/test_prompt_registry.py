import pytest
from app.prompts import prompt_registry, PromptRegistry

def test_prompt_registry_lists_categories():
    prompts = prompt_registry.list_prompts()
    assert "system_instructions" in prompts
    assert "image_gen" in prompts
    assert "video_gen" in prompts

def test_prompt_registry_renders_system_instructions():
    prompt = prompt_registry.get_prompt("system_instructions")
    assert "You are **BuddyCraft**" in prompt
    assert "Carol Gray" in prompt

def test_prompt_registry_renders_image_gen_with_variables():
    prompt = prompt_registry.get_prompt("image_gen", scene_prompt="Aarav sitting in dentist chair")
    assert "A soft 2D chibi cartoon storybook illustration" in prompt
    assert "Scene: Aarav sitting in dentist chair" in prompt

def test_prompt_registry_semver_resolution(tmp_path):
    # Create temporary prompt files to verify version sorting
    cat_dir = tmp_path / "custom_category"
    cat_dir.mkdir()
    
    v1_file = cat_dir / "v1.0.0.yaml"
    v1_file.write_text("""
metadata:
  name: test_prompt
  category: custom_category
  version: 1.0.0
template: "Version 1: {{ val }}"
""")

    v2_file = cat_dir / "v2.0.0.yaml"
    v2_file.write_text("""
metadata:
  name: test_prompt
  category: custom_category
  version: 2.0.0
template: "Version 2: {{ val }}"
""")

    registry = PromptRegistry(base_dir=str(tmp_path))
    
    # Latest should return v2.0.0
    latest = registry.get_prompt("custom_category", name="test_prompt", val="hello")
    assert latest == "Version 2: hello"
    
    # Explicit v1.0.0
    v1 = registry.get_prompt("custom_category", name="test_prompt", version="1.0.0", val="hello")
    assert v1 == "Version 1: hello"

def test_prompt_registry_missing_category_raises_keyerror():
    with pytest.raises(KeyError):
        prompt_registry.get_prompt("non_existent_category")
