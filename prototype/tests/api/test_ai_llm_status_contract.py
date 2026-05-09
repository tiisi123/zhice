from __future__ import annotations

import os

os.environ["DEBUG"] = "True"
os.environ.setdefault("ZHICE_JWT_SECRET", "test-secret-key-for-ci")
os.environ.setdefault("ZHICE_ADMIN_PASSWORD", "testadmin")
os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("ENCRYPTION_KEY", "_KdpjcJ4aDTICVpivJaELzNYQtGJs0syi5aevtQqXrM=")

from apps.api.routes import ai as ai_module


def test_llm_unavailable_text_maps_to_unavailable_status():
    status, message = ai_module._llm_contract_status(
        "AI 模型暂时不可用，已停止返回演示模板。请稍后重试。"
    )

    assert status == "unavailable"
    assert "产品侧 AI 网关" in message


def test_normal_llm_text_maps_to_real_status():
    status, message = ai_module._llm_contract_status("今日市场主线偏向算力。")

    assert status == "real"
    assert message == ""
