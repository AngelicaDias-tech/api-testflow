"""Importacao de massa de teste via CSV (melhoria "Massas de teste via
CSV") - parsing + validacao + previa, sem persistir nada (app/engine/
csv_import.py)."""

from __future__ import annotations

import pytest

from app.engine.csv_import import CsvImportError, parse_csv


def test_parse_csv_do_exemplo_do_pedido():
    csv_text = (
        "cpf,idade,valor,resultado_esperado\n"
        "12345678900,30,5000,aprovado\n"
        "11111111111,17,1000,recusado\n"
        "22222222222,18,2000,recusado\n"
    )
    result = parse_csv(csv_text)

    assert result["columns"] == ["cpf", "idade", "valor", "resultado_esperado"]
    assert len(result["rows"]) == 3
    assert result["errors"] == []
    # tipos numericos inferidos, cpf continua string (tem zero a esquerda em outros casos reais)
    assert result["rows"][0] == {
        "cpf": 12345678900,
        "idade": 30,
        "valor": 5000,
        "resultado_esperado": "aprovado",
    }


def test_parse_csv_vazio_levanta_erro():
    with pytest.raises(CsvImportError):
        parse_csv("")
    with pytest.raises(CsvImportError):
        parse_csv("   \n  ")


def test_parse_csv_cabecalho_com_coluna_vazia():
    with pytest.raises(CsvImportError):
        parse_csv("cpf,,valor\n123,1,10\n")


def test_parse_csv_cabecalho_duplicado():
    with pytest.raises(CsvImportError):
        parse_csv("cpf,cpf,valor\n123,456,10\n")


def test_parse_csv_linha_com_numero_errado_de_colunas_vira_erro_nao_bloqueante():
    csv_text = "cpf,idade\n123,30\n456\n789,20,extra\n"
    result = parse_csv(csv_text)

    assert len(result["rows"]) == 1  # so a linha 2 e valida
    assert len(result["errors"]) == 2
    assert "Linha 3" in result["errors"][0]
    assert "Linha 4" in result["errors"][1]


def test_parse_csv_ignora_linhas_em_branco():
    csv_text = "cpf,idade\n123,30\n\n456,20\n"
    result = parse_csv(csv_text)
    assert len(result["rows"]) == 2


def test_parse_csv_infere_booleanos():
    result = parse_csv("cpf,ativo\n123,true\n456,false\n")
    assert result["rows"][0]["ativo"] is True
    assert result["rows"][1]["ativo"] is False


def test_parse_csv_preserva_string_quando_nao_e_numero():
    result = parse_csv("cpf,nome\n123,Joao Silva\n")
    assert result["rows"][0]["nome"] == "Joao Silva"
    assert result["rows"][0]["cpf"] == 123
