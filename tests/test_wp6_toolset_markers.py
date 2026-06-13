"""WP6 acceptance tests: Portuguese toolset request markers."""

from __future__ import annotations

import pytest

from core.nl.toolsets import ToolsetName, toolsets_for_telegram_message


@pytest.mark.parametrize("message", [
    "apagar os módulos duplicados",
    "deletar essa nota",
    "excluir o módulo antigo",
    "remover o arquivo",
    "arquivar a nota velha",
    "limpar as entradas duplicadas",
    "duplicado encontrado, remover",
    "duplicar e mesclar entradas",
    "merge these duplicates please",
])
def test_portuguese_destructive_phrasing_selects_destructive_toolset(message: str) -> None:
    """Portuguese destructive phrases must add TELEGRAM_DESTRUCTIVE to the toolset."""
    toolsets = toolsets_for_telegram_message(message, web_enabled=True)
    assert ToolsetName.TELEGRAM_DESTRUCTIVE in toolsets, (
        f"Expected TELEGRAM_DESTRUCTIVE for message: {message!r}"
    )


@pytest.mark.parametrize("message", [
    "pesquisar na internet sobre redes neurais",
    "buscar na internet o que é transformer",
    "buscar na web sobre transformers",
    "na internet sobre python",
    "está online?",
])
def test_portuguese_web_phrasing_selects_egress_toolset(message: str) -> None:
    """Portuguese web phrases must add TELEGRAM_EGRESS when web_enabled=True."""
    toolsets = toolsets_for_telegram_message(message, web_enabled=True)
    assert ToolsetName.TELEGRAM_EGRESS in toolsets, (
        f"Expected TELEGRAM_EGRESS for message: {message!r}"
    )


@pytest.mark.parametrize("message", [
    "pesquisar na internet sobre redes neurais",
    "buscar na web python async",
])
def test_portuguese_web_phrasing_no_egress_when_web_disabled(message: str) -> None:
    """Egress toolset must not appear when web is disabled, even for Portuguese web phrases."""
    toolsets = toolsets_for_telegram_message(message, web_enabled=False)
    assert ToolsetName.TELEGRAM_EGRESS not in toolsets


@pytest.mark.parametrize("message", [
    "quais são meus próximos prazos?",
    "mostre-me o plano de estudo",
    "listar as minhas disciplinas",
    "adicionar nota sobre redes neurais",
])
def test_neutral_portuguese_messages_select_only_safe_toolset(message: str) -> None:
    """Neutral Portuguese messages must select only TELEGRAM_SAFE."""
    toolsets = toolsets_for_telegram_message(message, web_enabled=True)
    assert toolsets == {ToolsetName.TELEGRAM_SAFE}, (
        f"Expected only TELEGRAM_SAFE for neutral message: {message!r}"
    )
