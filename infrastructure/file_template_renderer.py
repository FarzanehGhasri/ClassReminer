"""
Concrete implementation of core.interfaces.TemplateRenderer.
Swap for a database- or CMS-backed renderer in a future project without
touching whatever calls it.
"""
import os

from core.interfaces import TemplateRenderer


class FileTemplateRenderer(TemplateRenderer):
    def __init__(self, templates_dir: str):
        self._templates_dir = templates_dir

    def render(self, template_name: str, **fields) -> str:
        path = os.path.join(self._templates_dir, template_name)
        with open(path, encoding="utf-8") as f:
            template_text = f.read().strip()
        try:
            return template_text.format(**fields)
        except KeyError as error:
            available = ", ".join(f"{{{key}}}" for key in fields)
            raise ValueError(
                f"Template '{template_name}' uses {{{error.args[0]}}}, which isn't a "
                f"supported placeholder. Available placeholders: {available}"
            ) from error