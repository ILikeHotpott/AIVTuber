from typing import Dict


class CharacterProvider:
    """Character setting provider"""

    def __init__(self):
        self._character_cache: Dict[str, str] = {}

    def get_character_prompt(self, character_name: str = "default") -> str:
        """Get character setting prompt"""
        if character_name in self._character_cache:
            return self._character_cache[character_name]

        # Try to load from file
        try:
            if character_name == "default":
                from src.prompt.templates.general import general_settings_prompt_english
                prompt = general_settings_prompt_english
            else:
                # Can be extended to support other character files
                prompt = self._load_character_from_file(character_name)

            self._character_cache[character_name] = prompt
            return prompt

        except ImportError:
            default_prompt = """
                You are an intelligent assistant dedicated to providing helpful, accurate, and safe responses to users.
                You should maintain a friendly and professional attitude and provide appropriate assistance based on user needs.
                """
            self._character_cache[character_name] = default_prompt
            return default_prompt

    def _load_character_from_file(self, character_name: str) -> str:
        """Load character settings from file"""
        # This can implement logic to load character settings from the file system
        # For example, loading from src/prompt/templates/characters/{character_name}.py
        raise ImportError(f"Character {character_name} not found")

    def update_character_cache(self, character_name: str, prompt: str):
        """Update character cache"""
        self._character_cache[character_name] = prompt

    def clear_cache(self):
        """Clear cache"""
        self._character_cache.clear()
