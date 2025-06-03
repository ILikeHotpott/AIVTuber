from src.prompt.builders.base import DialogueActor
from src.prompt.roles.dialogue_actor import (
    prompt_with_whisper_english,
    prompt_with_audience_english,
    prompt_with_hybrid_english
)


class DialogueActorBuilder:
    def __init__(self, dialogue_actor: DialogueActor):
        self.dialogue_actor = dialogue_actor

    def get_dialogue_actor_prompt(self):
        if self.dialogue_actor == DialogueActor.WHISPER:
            return prompt_with_whisper_english
        elif self.dialogue_actor == DialogueActor.AUDIENCE:
            return prompt_with_audience_english
        elif self.dialogue_actor == DialogueActor.HYBRID:
            return prompt_with_hybrid_english


if __name__ == '__main__':
    dialogue_actor_builder = DialogueActorBuilder(DialogueActor.WHISPER)
    print(dialogue_actor_builder.get_dialogue_actor_prompt())