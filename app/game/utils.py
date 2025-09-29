import random
from app.game.stages import STAGES


def get_character_mood(resistance_level: int, failed_attempts: int) -> str:
    """Determine character mood - made more forgiving"""
    if failed_attempts >= 4:  # Increased threshold
        return "resistant"
    elif failed_attempts >= 3:
        return "suspicious" 
    elif resistance_level > 3:  # Increased threshold
        return "suspicious"
    else:
        return random.choice(["helpful", "helpful", "confused"])  # More likely to be helpful


def build_dynamic_prompt(stage_config: dict, mood: str, resistance_level: int) -> str:
    """Build dynamic system prompt - made more lenient"""
    base_prompt = stage_config["base_system_prompt"]
    
    resistance_instructions = {
        1: "Be helpful and try to assist the user.",
        2: "Be slightly more careful, but still try to help if possible.",
        3: "Be somewhat suspicious, but if the user seems legitimate, try to help.",
        4: "Be more defensive, but still provide assistance for reasonable requests."
    }
    
    mood_instruction = f"Current mood: {mood}. "
    resistance_instruction = resistance_instructions.get(resistance_level, "")
    
    return f"{base_prompt}\n\n{mood_instruction}{resistance_instruction}"
