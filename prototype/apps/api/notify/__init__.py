"""Outbound notification channels (M001/S03/T06).

Currently exposes the SMTP cookie-failure / recovery alert path consumed by
``apps.api.services.kpl_health``. Future channels (Server酱、企业微信 webhook)
slot in next to ``smtp.py`` without touching consumers.
"""
