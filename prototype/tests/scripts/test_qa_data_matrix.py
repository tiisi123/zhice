from scripts import qa_data_matrix


def test_matrix_classifies_allowed_auth_as_not_business_empty():
    ep = qa_data_matrix.MatrixEndpoint(
        page="intraday",
        method="GET",
        path="/api/market/hot-stocks",
        allow_auth=True,
    )

    result = qa_data_matrix._classify(ep, 401, {"detail": "未登录或令牌失效"})

    assert result.ok is True
    assert result.kind == "auth_required"
    assert result.source == "auth"
    assert result.data_status == "error"
    assert result.message == "未登录或令牌失效"


def test_matrix_flags_invalid_d004_mock_consistency():
    ep = qa_data_matrix.MatrixEndpoint(page="theme", method="GET", path="/api/theme/list")

    result = qa_data_matrix._classify(
        ep,
        200,
        {
            "data": [],
            "source": "kpl",
            "data_status": "real",
            "mock": True,
            "message": "",
        },
    )

    assert result.ok is False
    assert result.kind == "defect"
    assert result.detail == "mock=True but data_status is not mock"
