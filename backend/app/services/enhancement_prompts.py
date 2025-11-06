from __future__ import annotations

from typing import Literal

PromptStyle = Literal["studio", "lifestyle", "creative"]

PROMPTS: dict[PromptStyle, str] = {
  "studio": (
    "A professional studio product photograph of the provided product on a clean "
    "white background with soft, even lighting. High-resolution, sharp focus."
  ),
  "lifestyle": (
    "A lifestyle product shot of the provided product on a modern wooden desk with a "
    "coffee cup nearby, natural window lighting, softly blurred background."
  ),
  "creative": (
    "A creative product shot of the provided product on a vibrant gradient background "
    "(blue to purple) with dramatic side lighting, studio quality."
  ),
}


def build_prompt(style: PromptStyle, product_name: str) -> str:
  base_prompt = PROMPTS[style]
  return (
    f"Generate an enhanced marketing image featuring the {product_name}. {base_prompt} "
    "Preserve the product's proportions and core design."
  )




