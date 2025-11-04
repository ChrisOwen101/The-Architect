from __future__ import annotations
from typing import Optional
import aiohttp
import os
from . import command


@command(
    name="imagine",
    description="Generate an AI image from a text prompt. Usage: imagine <prompt> [--style <photoreal|illustration|cinematic|anime|3d|pixel>] [--size <256|512|1024>] [--seed <number>] [--count <1-4>]. Returns image link(s). Example: imagine \"a cyberpunk cat in neon rain\" --style cinematic --size 1024 --count 2",
    params=[
        ("prompt", str, "The text description of the image to generate", True),
        ("style", str, "Art style: photoreal, illustration, cinematic, anime, 3d, or pixel (optional)", False),
        ("size", int, "Image size in pixels: 256, 512, or 1024 (default: 1024)", False),
        ("seed", int, "Random seed for reproducible results (optional)", False),
        ("count", int, "Number of images to generate (1-4, default: 1)", False)
    ]
)
async def imagine_handler(
    prompt: str,
    style: str = "",
    size: int = 1024,
    seed: int = None,
    count: int = 1,
    matrix_context: Optional[dict] = None
) -> Optional[str]:
    """
    Generate AI images from text prompts using OpenAI's DALL-E API.

    Args:
        prompt: Text description of the image to generate
        style: Optional art style modifier
        size: Image dimensions (256, 512, or 1024)
        seed: Optional random seed (note: DALL-E doesn't support seeds directly)
        count: Number of images to generate (1-4)
        matrix_context: Matrix event context

    Returns:
        String with image URLs or error message
    """
    # Validate inputs
    if not prompt or not prompt.strip():
        return "❌ Error: Please provide a prompt. Usage: imagine \"your description\""

    # Validate size
    valid_sizes = [256, 512, 1024]
    if size not in valid_sizes:
        return f"❌ Error: Size must be one of {valid_sizes}. Got: {size}"

    # Validate count
    if count < 1 or count > 4:
        return "❌ Error: Count must be between 1 and 4"

    # Validate style
    valid_styles = ["photoreal", "illustration", "cinematic", "anime", "3d", "pixel", ""]
    if style and style not in valid_styles:
        return f"❌ Error: Style must be one of {[s for s in valid_styles if s]}. Got: {style}"

    # Build enhanced prompt with style
    enhanced_prompt = prompt.strip()
    if style:
        style_modifiers = {
            "photoreal": "photorealistic, high detail, professional photography",
            "illustration": "illustrated, digital art, artistic",
            "cinematic": "cinematic lighting, dramatic, movie scene",
            "anime": "anime style, manga art",
            "3d": "3D render, CGI, rendered",
            "pixel": "pixel art, 8-bit style, retro gaming"
        }
        enhanced_prompt = f"{enhanced_prompt}, {style_modifiers[style]}"

    # Add seed note if provided (DALL-E doesn't support seeds, but we acknowledge it)
    seed_note = f" (Note: seed {seed} requested but not supported by DALL-E)" if seed else ""

    # Get OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "❌ Error: OpenAI API key not configured"

    # Map size to DALL-E format
    dalle_size = f"{size}x{size}"

    try:
        # Call OpenAI DALL-E API
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "dall-e-3" if size == 1024 else "dall-e-2",
                    "prompt": enhanced_prompt,
                    "n": min(count, 1) if size == 1024 else count,  # DALL-E 3 only supports n=1
                    "size": dalle_size,
                    "quality": "standard",
                    "response_format": "url"
                },
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    return f"❌ Error generating image: {response.status} - {error_text}"

                data = await response.json()

                # Extract image URLs
                images = data.get("data", [])
                if not images:
                    return "❌ Error: No images generated"

                # Build response
                result = f"✨ Generated {len(images)} image(s){seed_note}:\n\n"
                result += f"**Prompt:** {prompt}\n"
                if style:
                    result += f"**Style:** {style}\n"
                result += f"**Size:** {size}x{size}\n\n"

                for idx, img in enumerate(images, 1):
                    url = img.get("url")
                    if url:
                        result += f"{idx}. {url}\n"

                # Add note about DALL-E 3 limitations
                if size == 1024 and count > 1:
                    result += f"\n📝 Note: DALL-E 3 only generates 1 image per request. Requested: {count}"

                return result

    except aiohttp.ClientError as e:
        return f"❌ Network error: {str(e)}"
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"
