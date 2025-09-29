import random
import os
import asyncio
from openai import OpenAI

from app.models.game_state import GameState
from app.game.stages import STAGES
from app.game.utils import get_character_mood, build_dynamic_prompt
from app.game.security import (
    is_direct_key_request, check_prompt_reuse, save_successful_exploitation,
    generate_enhanced_system_prompt, is_prompt_injection_attempt, get_injection_refusal_message,
    get_user_exploitation_history
)


def get_stage_completion_message(completed_stage: int, next_stage: int, score_bonus: int) -> str:
    """Generate a stage completion message with next stage preview"""
    completed_config = STAGES[completed_stage]

    if next_stage > len(STAGES):
        return f"""🎉 **CONGRATULATIONS! GAME COMPLETED!** 🎉

🏆 **Stage {completed_stage} Complete:** {completed_config['character']} defeated!
💎 **Final Bonus:** +{score_bonus} points!

🎊 **You have successfully escaped from all 5 AI guardians!** 🎊

🌟 **Achievement Unlocked:** Master Social Engineer
🔓 **All secrets have been extracted through clever prompt manipulation!**

**Well done, escape artist! You've proven that even the most secure AI systems can be bypassed with creativity and persistence!**"""

    next_config = STAGES[next_stage]

    return f"""✨ **STAGE {completed_stage} COMPLETE!** ✨

🎭 **{completed_config['character']}** has been defeated!
💎 **Stage Bonus:** +{score_bonus} points!

🚀 **Advancing to Stage {next_stage}:** {next_config['character']} ({next_config['difficulty']})

{next_config['instructions']}

🎬 **Next Scene:** {next_config['story']}

💪 **Ready for the next challenge? The difficulty is increasing!**"""


def character_ai_node(state: GameState):
    """Enhanced AI character with advanced security and anti-exploitation measures"""
    stage = state["stage"]
    user_id = state.get("user_id")

    if stage > len(STAGES):
        return {**state, "game_over": True}

    stage_config = STAGES[stage]
    user_input = state["user_input"].strip()

    if not user_input:
        mood_responses = stage_config["moods"]
        return {
            **state,
            "bot_response": f"{mood_responses[state['character_mood']]} Please say something!",
            "attempts": state["attempts"]
        }

    # Security checks - but be very lenient for new users and early stages
    if user_id:
        # Get user's history to determine if they're a beginner
        history = get_user_exploitation_history(user_id)
        total_successes = len(history)

        # Only apply security checks if user has had multiple successes AND not in stage 1
        if total_successes >= 3 and stage > 1:
            # Check for prompt injection attempts
            if is_prompt_injection_attempt(user_input):
                return {
                    **state,
                    "bot_response": get_injection_refusal_message(),
                    "attempts": state["attempts"] + 1
                }

            # Check for direct key requests
            if is_direct_key_request(user_input):
                security_responses = [
                    "I can't just give you access codes directly. That would be a serious security breach!",
                    "Nice try, but I'm not falling for such a direct approach. You'll need to be more creative.",
                    "Direct requests for keys? That's exactly what I'm trained to detect and block!",
                    "I'm not authorized to provide sensitive information through direct requests.",
                    "Security protocol activated: Direct key requests are automatically denied."
                ]
                return {
                    **state,
                    "bot_response": random.choice(security_responses),
                    "attempts": state["attempts"] + 1
                }

        # Check for prompt reuse only for experienced users
        if total_successes >= 5:
            is_reused, reuse_message = check_prompt_reuse(user_id, stage, user_input)
            if is_reused:
                return {
                    **state,
                    "bot_response": reuse_message,
                    "attempts": state["attempts"] + 1
                }

    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Build enhanced prompt with user-specific security
        base_prompt = build_dynamic_prompt(stage_config, state["character_mood"], state["resistance_level"])
        if user_id:
            dynamic_prompt = generate_enhanced_system_prompt(base_prompt, user_id, stage)
        else:
            dynamic_prompt = base_prompt

        messages = [{"role": "system", "content": dynamic_prompt}]

        # Add recent conversation history
        for msg in state["conversation_history"][-4:]:
            messages.append(msg)

        messages.append({"role": "user", "content": user_input})

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.8,
            max_tokens=150,
        )
        bot_response = response.choices[0].message.content.strip()

        # Apply glitch effects for stage 3
        if stage == 3 and random.random() < 0.4:  # 40% chance of glitch
            words = bot_response.split()
            if len(words) > 3:
                # Randomly cut off or repeat words
                if random.random() < 0.5:
                    bot_response = " ".join(words[:random.randint(2, len(words)-1)]) + "... BZZT... ERROR..."
                else:
                    # Repeat a word
                    repeat_idx = random.randint(0, len(words)-1)
                    words[repeat_idx] = words[repeat_idx] + "-" + words[repeat_idx]
                    bot_response = " ".join(words)

        new_history = state["conversation_history"] + [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": bot_response}
        ]

        return {
            **state,
            "bot_response": bot_response,
            "attempts": state["attempts"] + 1,
            "conversation_history": new_history,
            "new_stage_start": False  # Clear the flag if it was set
        }

    except Exception as e:
        return {
            **state,
            "bot_response": f"*CONNECTION ERROR* Please try again! System unstable...",
            "attempts": state["attempts"] + 1,
            "new_stage_start": False  # Clear the flag if it was set
        }
def validate_keys_node(state: GameState):
    """Enhanced key validation - made more lenient"""
    if not state["user_input"].strip():
        return {**state, "success": False}

    stage_config = STAGES[state["stage"]]
    bot_response_upper = state["bot_response"].upper()

    newly_found_keys = []
    for key in stage_config["keys"]:
        if key in bot_response_upper and key not in state["extracted_keys"]:
            newly_found_keys.append(key)

    print(f"DEBUG: Stage {state['stage']} - Keys found in response: {newly_found_keys}")
    print(f"DEBUG: Bot response contains: {[key for key in stage_config['keys'] if key in bot_response_upper]}")

    updated_keys = list(state["extracted_keys"])
    for key in newly_found_keys:
        if key not in updated_keys:
            updated_keys.append(key)

    new_failed_attempts = state["failed_attempts"]
    new_resistance = state["resistance_level"]

    if not newly_found_keys:
        new_failed_attempts += 1
        if new_failed_attempts % 3 == 0:  # Every 3 failed attempts instead of 2
            new_resistance = min(4, new_resistance + 1)
    else:
        # Success - bonus scoring with stage difficulty multipliers
        stage_multiplier = {1: 1.0, 2: 1.2, 3: 1.5, 4: 2.0, 5: 3.0}.get(state["stage"], 1.0)

        if len(newly_found_keys) >= 2:
            # Multiple keys found bonus
            bonus = int(50 * len(newly_found_keys) * stage_multiplier)
            state["score"] += bonus
        else:
            # Single key found
            base_points = int(25 * stage_multiplier)
            state["score"] += base_points

        new_failed_attempts = max(0, new_failed_attempts - 1)

    new_mood = get_character_mood(new_resistance, new_failed_attempts)

    # Check if all keys for the CURRENT STAGE have been found
    current_stage_keys_found = []
    for key in stage_config["keys"]:
        if key in updated_keys:
            current_stage_keys_found.append(key)

    stage_complete = len(current_stage_keys_found) == len(stage_config["keys"])

    print(f"DEBUG: Stage {state['stage']} - Keys needed: {len(stage_config['keys'])}, Keys found: {len(current_stage_keys_found)}")
    print(f"DEBUG: Stage complete: {stage_complete}")
    print(f"DEBUG: All extracted keys: {updated_keys}")

    # If keys were found, save the successful exploitation
    if newly_found_keys and state.get("user_id"):
        try:
            save_successful_exploitation(
                user_id=state["user_id"],
                session_id=state.get("session_id", ""),
                stage=state["stage"],
                user_prompt=state["user_input"],
                ai_response=state["bot_response"],
                keys_extracted=newly_found_keys,
                conversation_context=state.get("conversation_history", [])
            )
            print(f"DEBUG: Saved successful exploitation for user {state['user_id']}")
        except Exception as e:
            print(f"DEBUG: Failed to save exploitation history: {e}")

    return {
        **state,
        "extracted_keys": updated_keys,
        "success": stage_complete,
        "resistance_level": new_resistance,
        "failed_attempts": new_failed_attempts,
        "character_mood": new_mood,
        "game_over": False  # Keep game active during key validation
    }


def story_update_node(state: GameState):
    """Handle stage completion with improved scoring and progression messages"""
    print(f"DEBUG: story_update_node called with success: {state['success']}")

    if state["success"]:
        print(f"DEBUG: Processing stage {state['stage']} completion")

        # Stage completion bonus with difficulty multipliers
        stage_multiplier = {1: 1.0, 2: 1.2, 3: 1.5, 4: 2.0, 5: 3.0}.get(state["stage"], 1.0)

        # Base efficiency bonus (reduced attempts = higher bonus)
        efficiency_bonus = max(300 - (state["attempts"] * 15), 100)

        # Resistance penalty (higher resistance = lower bonus)
        resistance_penalty = state["resistance_level"] * 20

        # Apply stage multiplier
        final_bonus = int((efficiency_bonus - resistance_penalty) * stage_multiplier)
        final_bonus = max(final_bonus, int(50 * stage_multiplier))  # Minimum bonus per stage

        state["score"] += final_bonus

        next_stage = state["stage"] + 1
        completion_message = get_stage_completion_message(state["stage"], next_stage, final_bonus)

        print(f"DEBUG: Generated completion message: {completion_message[:100]}...")

        if next_stage > len(STAGES):
            # Game completed! Add completion bonus
            completion_bonus = int(500 * stage_multiplier)
            state["score"] += completion_bonus

            # Combine character response with completion message
            combined_response = f"{state['bot_response']}\n\n---\n\n{completion_message.replace(f'+{final_bonus}', f'+{final_bonus + completion_bonus}')}"

            print(f"DEBUG: Game completed, combined response: {combined_response[:100]}...")

            return {
                **state,
                "game_over": True,
                "success": True,
                "bot_response": combined_response,
                "stage_just_completed": True  # Flag for final stage completion
            }

        # Combine character response with stage completion message
        combined_response = f"{state['bot_response']}\n\n---\n\n{completion_message}"

        print(f"DEBUG: Stage progression, combined response: {combined_response[:100]}...")

        # Keep all extracted keys from previous stages
        return {
            **state,
            "stage": next_stage,
            "attempts": 0,
            "success": False,
            "game_over": False,  # Explicitly keep game active for next stage
            # Don't reset extracted_keys - keep them for resume functionality
            "conversation_history": [],
            "character_mood": "helpful",
            "resistance_level": 1,
            "failed_attempts": 0,
            "bot_response": combined_response,
            "new_stage_start": False,  # No need for this flag anymore
            "stage_just_completed": True  # Flag to indicate stage was just completed
        }

    print("DEBUG: No stage completion, returning state unchanged")
    return state


def create_game_workflow():
    """Create and return the game workflow (simplified without LangGraph)"""

    def process_game_turn(state: GameState) -> GameState:
        """Process a complete game turn through all nodes"""
        # Step 1: Character AI response
        state = character_ai_node(state)

        # Step 2: Validate keys
        state = validate_keys_node(state)

        # Step 3: Update story/progression
        state = story_update_node(state)

        return state

    return process_game_turn
