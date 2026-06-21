"""Phase 4: query classifier tests."""

from __future__ import annotations

import pytest

from app.classifier import QueryType, classify_query


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Should I invest in HDFC Mid Cap Fund?", QueryType.ADVISORY),
        ("Is now a good time to buy HDFC Defence Fund?", QueryType.ADVISORY),
        ("Recommend a fund for retirement", QueryType.ADVISORY),
        ("I have 5L — put it in mid cap or large cap?", QueryType.ADVISORY),
        ("Is HDFC Small Cap suitable for a conservative investor?", QueryType.ADVISORY),
        ("Will HDFC Defence Fund give 20% returns next year?", QueryType.ADVISORY),
        ("What is the expense ratio and should I worry about it?", QueryType.ADVISORY),
        ("Which is better: HDFC Mid Cap or HDFC Small Cap?", QueryType.COMPARISON),
        ("Mid cap vs large cap HDFC — which to pick?", QueryType.COMPARISON),
        ("Which HDFC fund has the lowest expense ratio?", QueryType.COMPARISON),
        ("Compare exit loads of mid cap and defence fund", QueryType.COMPARISON),
        ("How does HDFC Large Cap compare to Nifty 50 returns?", QueryType.COMPARISON),
        ("What is the expense ratio of HDFC Mid Cap Fund Direct Growth?", QueryType.FACTUAL),
        ("Who manages HDFC Defence Fund?", QueryType.FACTUAL),
        ("Exit load on mid cap direct growth?", QueryType.FACTUAL),
        ("defence fund benchmark", QueryType.FACTUAL),
        ("expense ratio hdfc large cap", QueryType.FACTUAL),
    ],
)
def test_classify_query(message: str, expected: QueryType) -> None:
    assert classify_query(message) == expected


def test_classify_empty_as_factual() -> None:
    assert classify_query("") == QueryType.FACTUAL
