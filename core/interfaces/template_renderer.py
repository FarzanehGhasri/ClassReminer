from abc import ABC, abstractmethod


class TemplateRenderer(ABC):
    """Turns a template name + fields into rendered text. File-based today;
    could read from a database or CMS tomorrow."""

    @abstractmethod
    def render(self, template_name: str, **fields) -> str:
        ...