"""
Shows exactly what the project is reading from .env, to catch cases
where .env isn't being found/loaded, or has stale/wrong values.
Run from the project root: python check_config.py
"""
from config import settings

print("SMTP_HOST:", repr(settings.SMTP_HOST))
print("SMTP_PORT:", repr(settings.SMTP_PORT), "(should be 587)")
print("SMTP_USERNAME:", repr(settings.SMTP_USERNAME))
print("SMTP_PASSWORD length:", len(settings.SMTP_PASSWORD), "(should be 16)")
print("SMTP_PASSWORD repr:", repr(settings.SMTP_PASSWORD))
