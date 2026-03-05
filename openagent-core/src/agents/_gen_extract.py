
# -*- coding: utf-8 -*-
"""Generator script: writes extract_dcre.py to the dcre_regex_extractor folder."""
import os

TARGET = os.path.join(
    'Lighthouse', 'Projetos', 'Tax', 'DCRe',
    'dcre_regex_extractor', 'extract_dcre.py'
)

CODE = r'''# -*- coding: utf-8 -*-
"""
Extrator de dados DCR-E a partir de arquivos TXT (OCR de PDFs).
Utiliza regex para extrair campos estruturados dos documentos DCR-E,
produzindo saida compativel com os modelos Pydantic definidos.

Autor: Coder Agent
Data: 2025
"""

import re
import os
import json
import sys
from typing import Optional


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def _strip_html(text: str) -> str:
    """Remove tags HTML mantendo o conteudo textual."""
    text = re.sub(r'</t[dhr]>', '\t', text)
    text = re.sub(r'</tr>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    return text


def _parse_br_float(text: str) -> float:
    """Converte numero brasileiro ('1.234,56' ou '1,56') para float."""
    if not text or not text.strip():
        return 0.0
    text = text.strip().replace(" ", "").replace("%", "")
    text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _td_after(text: str, label: str) -> str:
    """Retorna conteudo do primeiro <td> nao-vazio apos label</td>."""
    pattern = (
        re.escape(label) + r"\s*</td>"
        r"(?:\s*<td[^>]*>\s*</td>)*"
        r"\s*<td[^>]*>\s*(.*?)\s*</td>"
    )
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else ""


def _search(pattern: str, text: str, group: int = 1) -> str:
    """Busca regex e retorna grupo, ou string vazia."""
    m = re.search(pattern, text, re.DOTALL)
    return m.group(group).strip() if m else ""


def _find_decimal_values(text: str) -> list:
    """Encontra todos valores decimais com >=4 casas apos virgula em tds."""
    return re.findall(r">\s*(\d+,\d{4,})\s*<", text)


# ---------------------------------------------------------------------------
# Extracao do Resumo - Formato Tabela HTML
# ---------------------------------------------------------------------------

def _extract_resumo_table(resumo_text: str) -> dict:
    """Extrai campos do resumo quando em formato tabela HTML."""
    r = {}

    r['cnpj'] = _td_after(resumo_text, "CNPJ:")
    r['razao_social'] = _td_after(resumo_text, "Raz\u00e3o Social:")
    r['representante_legal'] = _td_after(resumo_text, "Representante Legal:")
    r['denominacao_produto'] = _td_after(resumo_text, "Denomina\u00e7\u00e3o do Produto:")
    r['codigo_ncm'] = _td_after(resumo_text, "C\u00f3digo NCM:")

    peso = _td_after(resumo_text, "Peso Bruto:")
    r['peso_bruto'] = _parse_br_float(peso) if peso else None

    r['unidade'] = _td_after(resumo_text, "Unidade:")
    r['processo_produtivo_basico'] = _td_after(resumo_text, "Processo Produtivo B\u00e1sico:")

    sal = _td_after(resumo_text, "Custos - Sal\u00e1rios e Ordenados:")
    r['custos_salarios_ordenados'] = _parse_br_float(sal) if sal else None

    # Encargos - campo problematico, pode estar em rowspan
    enc = _td_after(resumo_text, "Custos - Encargos Sociais e Trabalhistas:")
    if not enc:
        m = re.search(
            r'Encargos\s+Sociais\s+e\s+Trabalhistas\s*:?\s*</td>'
            r'(?:\s*<td[^>]*>\s*</td>)*'
            r'(?:\s*</tr>\s*<tr>\s*)?'
            r'\s*<td[^>]*>\s*([\d,.]+)\s*</td>',
            resumo_text, re.DOTALL | re.IGNORECASE
        )
        enc = m.group(1) if m else ""
    r['custos_encargos_sociais_trabalhistas'] = _parse_br_float(enc) if enc else None

    r['tipo_coeficiente_reducao'] = _td_after(resumo_text, "Tipo de Coeficiente de Redu\u00e7\u00e3o:")
    r['tipo_dcre'] = _td_after(resumo_text, "Tipo DCR-E:")

    # Campos de custo - podem estar quebrados entre <td>s
    for field_name, label in [
        ('custo_componentes_nacionais_usd', 'Custo dos Componentes Nacionais'),
        ('custo_componentes_importados_usd', 'Custo dos Componentes Importados'),
        ('custo_mao_de_obra_usd', 'Custo de M\u00e3o-de-obra'),
        ('custo_total_usd', 'Custo Total'),
        ('valor_total_ii_sem_reducao_usd', 'Valor Total do II sem Redu\u00e7\u00e3o'),
        ('valor_total_ii_com_reducao_usd', 'Valor Total do II com Redu\u00e7\u00e3o'),
    ]:
        val = _td_after(resumo_text, label + " (US$):")
        if not val:
            # Label quebrado: label em um td, (US$): em outro
            m = re.search(
                re.escape(label) + r'.*?(?:\(US\$\)\s*:?\s*</td>)'
                r'\s*(?:<td[^>]*>\s*</td>)*\s*<td[^>]*>\s*([\d,.]+)\s*</td>',
                resumo_text, re.DOTALL | re.IGNORECASE
            )
            val = m.group(1) if m else ""
        if not val:
            # Fallback: label + qualquer coisa + valor
            plain = _strip_html(resumo_text)
            m = re.search(
                re.escape(label) + r'[^\d]*?([\d][\d,.]+)',
                plain, re.IGNORECASE | re.DOTALL
            )
            val = m.group(1) if m else ""
        r[field_name] = _parse_br_float(val) if val else None

    # Coeficiente de Reducao do II
    m = re.search(
        r'Coeficiente de Redu\u00e7\u00e3o do II\s*:?\s*</td>'
        r'\s*(?:<td[^>]*>\s*</td>)*\s*<td[^>]*>\s*([\d,.]+)\s*%',
        resumo_text, re.DOTALL
    )
    if not m:
        plain = _strip_html(resumo_text)
        m = re.search(
            r'Coeficiente de Redu.{1,10} do II\s*:?\s*\n?\s*([\d,.]+)\s*%',
            plain, re.IGNORECASE
        )
    r['coeficiente_reducao_ii_percentual'] = _parse_br_float(m.group(1)) if m else None

    return r


# ---------------------------------------------------------------------------
# Extracao do Resumo - Formato Texto Plano
# ---------------------------------------------------------------------------

def _extract_resumo_plain(resumo_text: str) -> dict:
    """Extrai campos do resumo quando em formato texto plano (sem tabela)."""
    r = {}
    plain = _strip_html(resumo_text)

    def get_val(label_pattern):
        m = re.search(label_pattern + r'\s*:?\s*\n+\s*(.+?)(?:\n|$)', plain, re.IGNORECASE)
        return m.group(1).strip() if m else ""

    r['cnpj'] = get_val(r'CNPJ')
    r['razao_social'] = get_val(r'Raz.{1,5}Social')
    r['representante_legal'] = get_val(r'Representante\s+Legal')

    # Denominacao pode ter quebra de linha
    m = re.search(
        r'Denomina.{1,10}Produto\s*:\s*\n(.+?)(?=\nC.{1,5}digo\s+NCM|\nC.{1,5}NCM)',
        plain, re.DOTALL | re.IGNORECASE
    )
    r['denominacao_produto'] = re.sub(r'\s+', ' ', m.group(1)).strip() if m else ""

    r['codigo_ncm'] = get_val(r'C.{1,5}digo\s+NCM')

    peso = get_val(r'Peso\s+Bruto')
    r['peso_bruto'] = _parse_br_float(peso) if peso else None

    r['unidade'] = get_val(r'Unidade')
    r['processo_produtivo_basico'] = get_val(r'Processo\s+Produtivo\s+B.{1,5}sico')

    sal = get_val(r'Sal.{1,5}rios\s+e\s+Ordenados')
    r['custos_salarios_ordenados'] = _parse_br_float(sal) if sal else None

    enc = get_val(r'Trabalhistas')
    r['custos_encargos_sociais_trabalhistas'] = _parse_br_float(enc) if enc else None

    r['tipo_coeficiente_reducao'] = get_val(r'Tipo\s+de\s+Coeficiente')
    r['tipo_dcre'] = get_val(r'Tipo\s+DCR-E')

    # Campos de custo com possivel quebra de linha
    for field_name, label_pat in [
        ('custo_componentes_nacionais_usd', r'Componentes\s+Nacionais[^\d]*?\(US\$\)'),
        ('custo_componentes_importados_usd', r'Componentes\s+Importados[^\d]*?\(US\$\)'),
        ('custo_mao_de_obra_usd', r'M.{1,5}o-de-obra[^\d]*?\(US\$\)'),
        ('custo_total_usd', r'Custo\s+Total[^\d]*?\(US\$\)'),
        ('valor_total_ii_sem_reducao_usd', r'II\s+sem\s+Redu[^\d]*?\(US\$\)'),
        ('valor_total_ii_com_reducao_usd', r'II\s+com\s+Redu[^\d]*?\(US\$\)'),
    ]:
        m = re.search(label_pat + r'\s*:?\s*\n?\s*([\d,.]+)', plain, re.IGNORECASE | re.DOTALL)
        r[field_name] = _parse_br_float(m.group(1)) if m else None

    m = re.search(r'Coeficiente\s+de\s+Redu.{1,10}do\s+II\s*:?\s*\n?\s*([\d,.]+)\s*%', plain, re.IGNORECASE)
    r['coeficiente_reducao_ii_percentual'] = _parse_br_float(m.group(1)) if m else None

    return r


# ---------------------------------------------------------------------------
# Extracao do Resumo - Funcao Principal
# ---------------------------------------------------------------------------

def extract_resumo(text: str) -> dict:
    """Extrai todos os campos do Resumo DCR-E."""
    resumo = {}

    # --- Numero DCR-E (do Comprovante) ---
    m = re.search(
        r'N.{1,10}mero\s+do\s+DCR-E\s*:\s*</td>\s*<td[^>]*>\s*(\d{4}/\d+-\d)',
        text, re.IGNORECASE
    )
    if not m:
        m = re.search(r'Resumo do DCRE\s*:\s*(\d{4}/\d+-\d)', text, re.IGNORECASE)
    if not m:
        plain = _strip_html(text)
        m = re.search(r'N.{1,10}mero\s+do\s+DCR-E\s*:\s*\n?\s*(\d{4}/\d+-\d)', plain, re.IGNORECASE)
    resumo['numero_dcre'] = m.group(1).strip() if m else None

    # --- Data Recepcao (do Comprovante) ---
    m = re.search(
        r'Data\s+do\s+Registro\s*:\s*</td>\s*<td[^>]*>\s*(\d{2}/\d{2}/\d{4})',
        text, re.IGNORECASE
    )
    if not m:
        plain = _strip_html(text)
        m = re.search(r'Data\s+d[ao]\s+(?:Registro|Recep.{1,5}o)\s*:\s*\n?\s*(\d{2}/\d{2}/\d{4})', plain, re.IGNORECASE)
    resumo['data_recepcao'] = m.group(1).strip() if m else None

    # --- Hora Recepcao (do Comprovante) ---
    m = re.search(
        r'Hora\s+do\s+Registro\s*:\s*</td>\s*<td[^>]*>\s*(\d{2}:\d{2})',
        text, re.IGNORECASE
    )
    if not m:
        plain = _strip_html(text)
        m = re.search(r'Hora\s+d[ao]\s+(?:Registro|Recep.{1,5}o)\s*:\s*\n?\s*(\d{2}:\d{2})', plain, re.IGNORECASE)
    resumo['hora_recepcao'] = m.group(1).strip() if m else None

    # --- Encontra secao do Resumo ---
    resumo_table = re.search(
        r'Resumo do DCRE\s*:.*?(<table>.*?</table>)',
        text, re.DOTALL | re.IGNORECASE
    )

    resumo_plain = re.search(
        r'Resumo da Declara.{1,10}\n(.+?)(?=Modelos\s*/\s*Tipos|detalhar|<!-- Page)',
        text, re.DOTALL | re.IGNORECASE
    )

    if resumo_table:
        fields = _extract_resumo_table(resumo_table.group(1))
    elif resumo_plain:
        fields = _extract_resumo_plain(resumo_plain.group(0))
    else:
        fields = _extract_resumo_table(text)

    for k, v in fields.items():
        if k not in resumo or resumo[k] is None:
            if isinstance(v, str) and not v:
                resumo[k] = None
            else:
                resumo[k] = v

    return resumo


# ---------------------------------------------------------------------------
# Extracao de Modelos/Tipos/Referencias
# ---------------------------------------------------------------------------

def extract_modelos(text: str) -> list:
    """Extrai a lista de Modelos/Tipos/Referencias."""
    modelos = []

    m = re.search(r'Pre.{1,5}o\s+de\s+Venda', text, re.IGNORECASE)
    if not m:
        return modelos

    after_header = text[m.end():]
    end_table = after_header.find("</table>")
    table_body = after_header[:end_table] if end_table != -1 else after_header[:3000]

    rows = re.findall(r"<tr>(.*?)</tr>", table_body, re.DOTALL)
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        cells = [c.strip() for c in cells if c.strip()]
        if len(cells) >= 3:
            espec = cells[0]
            codigo = cells[1]
            preco = cells[2]
            if 'Especifica' in espec or 'Codigo' in espec:
                continue
            modelos.append({
                'especificacao': espec,
                'codigo_interno': codigo,
                'preco_venda_usd': _parse_br_float(preco),
            })

    # Formato texto plano
    if not modelos:
        plain = _strip_html(after_header[:3000])
        lines = [l.strip() for l in plain.split('\n') if l.strip()]
        i = 0
        while i < len(lines):
            if any(kw in lines[i] for kw in ['Especifica', 'Codigo', 'Preco', 'retornar', 'http']):
                i += 1
                continue
            if i + 2 < len(lines):
                preco_str = lines[i + 2]
                if re.match(r'^[\d,.]+$', preco_str):
                    modelos.append({
                        'especificacao': lines[i],
                        'codigo_interno': lines[i + 1],
                        'preco_venda_usd': _parse_br_float(preco_str),
                    })
                    i += 3
                    continue
            i += 1

    return modelos


# ---------------------------------------------------------------------------
# Extracao de Componentes Nacionais
# ---------------------------------------------------------------------------

def extract_componentes_nacionais(text: str) -> list:
    """Extrai componentes nacionais usando posicoes de 'NF' como ancora."""
    componentes = []

    nf_pattern = r'N.{0,3}\s*NF\s*:'
    nac_match = re.search(r'COMPONENTES\s+NACIONAIS', text, re.IGNORECASE)
    if nac_match is None:
        return componentes
    nac_start = nac_match.end()

    imp_match = re.search(r'COMPONENTES\s+IMPORTADOS', text, re.IGNORECASE)
    nac_end = imp_match.start() if imp_match else None

    nac_text = text[nac_start:nac_end] if nac_end else text[nac_start:]
    nf_positions = [m.start() for m in re.finditer(nf_pattern, nac_text, re.IGNORECASE)]

    for idx, pos in enumerate(nf_positions):
        next_pos = nf_positions[idx + 1] if idx + 1 < len(nf_positions) else pos + 2000
        blk = nac_text[pos:min(next_pos, pos + 2000)]

        nf_val = _search(r'N.{0,3}\s*NF\s*:\s*(?:</td>\s*<td[^>]*>\s*)?(\d+)', blk)

        serie_data_raw = _search(r'S.{1,3}rie\s*:\s*(?:</td>\s*<td[^>]*>\s*)?(.*?)\s*</td>', blk)
        if not serie_data_raw:
            serie_data_raw = _search(r'S.{1,3}rie\s*:\s*(.+?)(?:\n|$)', _strip_html(blk))

        sd = re.match(r'(\S+)\s*(?:[Dd]ata:\s*([\d/]+))?', serie_data_raw or "")
        serie = sd.group(1) if sd and sd.group(1) else ""
        data = sd.group(2) if sd and sd.group(2) else ""
        if not data:
            data = _search(r'[Dd]ata\s*:\s*(\d{2}/\d{2}/\d{4})', blk)

        cnpj = _search(r'CNPJ\s*:\s*(?:</td>\s*<td[^>]*>\s*)?([\d./\-]+)', blk)
        insc = _search(r'Ins\.?\s*Est\s*\.?\s*\.?\s*:?\s*(?:</td>\s*<td[^>]*>)?\s*(\d+)', blk)
        ncm = _search(r'NCM\s*:\s*(?:</td>\s*<td[^>]*>\s*)?([\d.]+)', blk)
        unid = _search(r'Unidade\s*:\s*(?:</td>\s*<td[^>]*>)?\s*([A-Z]+)', blk)

        all_vals = _find_decimal_values(blk)
        qty = all_vals[0] if len(all_vals) >= 1 else "0"
        v_unit = all_vals[1] if len(all_vals) >= 2 else "0"
        v_tot = all_vals[2] if len(all_vals) >= 3 else "0"

        # Especificacao
        if idx == 0:
            header_pos = nac_text.rfind("NACIONAIS", 0, pos)
            if header_pos == -1:
                header_pos = 0
            blk_start = nac_text.find("</tr>", header_pos)
            blk_start = blk_start + 5 if blk_start != -1 and blk_start < pos else 0
        else:
            prev_ncm = nac_text.rfind("NCM:", nf_positions[idx - 1], pos)
            if prev_ncm != -1:
                blk_start = nac_text.find("</tr>", prev_ncm)
                blk_start = blk_start + 5 if blk_start != -1 else nf_positions[idx - 1]
            else:
                prev_unid = nac_text.rfind("Unidade:", nf_positions[idx - 1], pos)
                if prev_unid != -1:
                    blk_start = nac_text.find("</tr>", prev_unid)
                    blk_start = blk_start + 5 if blk_start != -1 else nf_positions[idx - 1]
                else:
                    blk_start = nf_positions[idx - 1]

        pre = nac_text[blk_start:pos]
        spec_parts = re.findall(r'<td[^>]*>([^<]+)</td>', pre)
        spec_parts = [
            s.strip() for s in spec_parts
            if s.strip() and s.strip() not in ("", "detalhar", "retornar")
            and not s.strip().startswith("http")
        ]
        especificacao = " ".join(spec_parts)
        especificacao = re.sub(r'^\d+\s+', '', especificacao)

        if not especificacao:
            pre_text = _strip_html(pre).strip()
            pre_text = re.sub(r'<!--.*?-->', '', pre_text).strip()
            lines = [l.strip() for l in pre_text.split('\n') if l.strip()
                     and not l.strip().startswith('http')
                     and 'PageHeader' not in l
                     and 'Demonstrativo' not in l
                     and 'CNPJ' not in l
                     and 'Data:' not in l]
            especificacao = " ".join(lines)
            especificacao = re.sub(r'^\d+\s+', '', especificacao)

        componentes.append({
            'item': idx + 1,
            'especificacao': especificacao or None,
            'numero_nf': nf_val or None,
            'serie': serie or None,
            'data': data or None,
            'cnpj': cnpj or None,
            'inscricao_estadual': insc or None,
            'codigo_ncm': ncm or None,
            'unidade': unid.upper() if unid else None,
            'quantidade': _parse_br_float(qty),
            'valor_unitario_usd': _parse_br_float(v_unit),
            'valor_total_usd': _parse_br_float(v_tot),
        })

    return componentes


# ---------------------------------------------------------------------------
# Extracao de Componentes Importados
# ---------------------------------------------------------------------------

def extract_componentes_importados(text: str) -> list:
    """Extrai componentes importados usando posicoes de 'DI:' como ancora."""
    componentes = []

    imp_matches = list(re.finditer(r'COMPONENTES\s+IMPORTADOS', text, re.IGNORECASE))
    if not imp_matches:
        return componentes

    imp_start = imp_matches[0].end()
    imp_text = text[imp_start:]

    di_pattern = r'DI\s*:\s*</td>'
    di_matches_list = list(re.finditer(di_pattern, imp_text, re.IGNORECASE))

    if not di_matches_list:
        di_pattern = r'<td[^>]*>\s*DI\s*:\s*</td>'
        di_matches_list = list(re.finditer(di_pattern, imp_text, re.IGNORECASE))

    if not di_matches_list:
        di_pattern = r'DI\s*:\s*(?:\s*\d{2}/\d+)'
        di_matches_list = list(re.finditer(di_pattern, imp_text, re.IGNORECASE))

    for idx, di_m in enumerate(di_matches_list):
        pos = di_m.start()
        next_pos = di_matches_list[idx + 1].start() if idx + 1 < len(di_matches_list) else pos + 2000
        blk = imp_text[pos:min(next_pos, pos + 2000)]

        di_val = _search(r'DI\s*:\s*(?:</td>\s*<td[^>]*>\s*)?([\d/\-]+)', blk)
        cnpj = _search(r'CNPJ\s*:\s*(?:</td>\s*<td[^>]*>\s*)?([\d./\-]+)', blk)
        adicao = _search(r'Adi.{1,5}o\s*:\s*(?:</td>\s*<td[^>]*>\s*)?(\d+)', blk)
        item_adicao = _search(r'Item\s*:\s*(?:</td>\s*<td[^>]*>\s*)?(\d+)', blk)
        ncm = _search(r'NCM\s*:\s*(?:</td>\s*<td[^>]*>\s*)?([\d.]+)', blk)
        aliq = _search(r'Al.{1,5}quota\s*:\s*(?:</td>\s*<td[^>]*>\s*)?([\d,.]+)', blk) or "0"
        susp = _search(r'Suspens.{1,5}o\s*:\s*(?:</td>\s*<td[^>]*>\s*)?(\S+)', blk)
        red = _search(r'Redu.{1,5}o\s+II\s*:\s*(?:</td>\s*<td[^>]*>\s*)?(\S+)', blk)
        unid = _search(r'Unidade\s*:\s*(?:</td>\s*<td[^>]*>)?\s*([A-Z]+)', blk)

        all_vals = _find_decimal_values(blk)
        qty = all_vals[0] if len(all_vals) >= 1 else "0"
        v_unit = all_vals[1] if len(all_vals) >= 2 else "0"
        v_tot = all_vals[2] if len(all_vals) >= 3 else "0"
        v_ii = all_vals[3] if len(all_vals) >= 4 else "0"

        # Especificacao
        if idx == 0:
            header_pos = imp_text.rfind("IMPORTADOS", 0, pos)
            if header_pos == -1:
                header_pos = 0
            blk_start = imp_text.find("</tr>", header_pos)
            blk_start = blk_start + 5 if blk_start != -1 and blk_start < pos else 0
        else:
            prev_unit = imp_text.rfind("Unidade:", di_matches_list[idx - 1].end(), pos)
            if prev_unit != -1:
                blk_start = imp_text.find("</tr>", prev_unit)
                blk_start = blk_start + 5 if blk_start != -1 else di_matches_list[idx - 1].end()
            else:
                blk_start = di_matches_list[idx - 1].end()

        pre = imp_text[blk_start:pos]
        spec_parts = re.findall(r'<td\s+colspan="[0-9]+">(.*?)</td>', pre, re.DOTALL)
        especificacao = " ".join(s.strip() for s in spec_parts if s.strip())
        especificacao = re.sub(r'^\d+\s+', '', especificacao)

        if not especificacao:
            spec_parts2 = re.findall(r'<td[^>]*>([^<]+)</td>', pre)
            spec_parts2 = [s.strip() for s in spec_parts2
                          if s.strip() and s.strip() not in ("", "detalhar", "retornar")
                          and not s.strip().startswith("http")]
            especificacao = " ".join(spec_parts2)
            especificacao = re.sub(r'^\d+\s+', '', especificacao)

        if not especificacao:
            pre_text = _strip_html(pre).strip()
            pre_text = re.sub(r'<!--.*?-->', '', pre_text).strip()
            lines = [l.strip() for l in pre_text.split('\n') if l.strip()
                     and not l.strip().startswith('http')
                     and 'PageHeader' not in l
                     and 'Demonstrativo' not in l
                     and 'CNPJ' not in l
                     and 'Data:' not in l
                     and 'Numero:' not in l]
            especificacao = " ".join(lines)
            especificacao = re.sub(r'^\d+\s+', '', especificacao)

        componentes.append({
            'item': idx + 1,
            'especificacao': especificacao or None,
            'di': di_val or None,
            'cnpj': cnpj or None,
            'adicao': adicao or None,
            'item_adicao': item_adicao or None,
            'quantidade': _parse_br_float(qty),
            'valor_unitario_usd': _parse_br_float(v_unit),
            'valor_total_usd': _parse_br_float(v_tot),
            'valor_ii_usd': _parse_br_float(v_ii),
            'codigo_ncm': ncm or None,
            'aliquota': _parse_br_float(aliq),
            'suspensao': susp or None,
            'reducao_ii': red or None,
            'unidade': unid.upper() if unid else None,
        })

    return componentes


# ---------------------------------------------------------------------------
# Funcao principal de extracao
# ---------------------------------------------------------------------------

def extract_dcre(filepath: str) -> dict:
    """Extrai todos os dados de um arquivo TXT de DCR-E."""
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    resumo = extract_resumo(text)
    modelos = extract_modelos(text)
    nacionais = extract_componentes_nacionais(text)
    importados = extract_componentes_importados(text)

    return {
        'resumo': resumo,
        'componentes_nacionais': nacionais,
        'componentes_importados': importados,
        'modelos_tipos_referencias': modelos,
    }


def extract_all(input_dir: str, output_dir: str = None) -> dict:
    """Extrai dados de todos os arquivos TXT em um diretorio."""
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    files = [f for f in os.listdir(input_dir) if f.endswith('.txt')]
    results = {}
    stats = {
        'total_files': len(files),
        'successful': 0,
        'failed': 0,
        'field_stats': {},
    }

    for filename in sorted(files):
        filepath = os.path.join(input_dir, filename)
        try:
            data = extract_dcre(filepath)
            results[filename] = data
            stats['successful'] += 1

            if data.get('resumo'):
                for key, val in data['resumo'].items():
                    if key not in stats['field_stats']:
                        stats['field_stats'][key] = {'found': 0, 'missing': 0}
                    if val is not None:
                        stats['field_stats'][key]['found'] += 1
                    else:
                        stats['field_stats'][key]['missing'] += 1

            if output_dir:
                json_name = os.path.splitext(filename)[0] + '.json'
                json_path = os.path.join(output_dir, json_name)
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            import traceback
            results[filename] = {'error': str(e)}
            stats['failed'] += 1
            print(f"ERRO ao processar {filename}: {e}")
            traceback.print_exc()

    return {'results': results, 'stats': stats}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    input_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data', 'output', 'txt'
    )
    output_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'output_json'
    )

    print(f"Processando arquivos de: {input_dir}")
    print(f"Salvando JSONs em: {output_dir}")
    print()

    result = extract_all(input_dir, output_dir)
    stats = result['stats']

    print(f"\n{'='*60}")
    print(f"ESTATISTICAS DE EXTRACAO")
    print(f"{'='*60}")
    print(f"Total de arquivos: {stats['total_files']}")
    print(f"Processados com sucesso: {stats['successful']}")
    print(f"Falhas: {stats['failed']}")
    print()

    print(f"{'Campo':<45} {'Encontrado':>10} {'Faltando':>10} {'Taxa':>8}")
    print(f"{'-'*75}")

    total_found = 0
    total_fields = 0

    for field, counts in sorted(stats['field_stats'].items()):
        found = counts['found']
        missing = counts['missing']
        total = found + missing
        rate = (found / total * 100) if total > 0 else 0
        total_found += found
        total_fields += total
        print(f"{field:<45} {found:>10} {missing:>10} {rate:>7.1f}%")

    overall_rate = (total_found / total_fields * 100) if total_fields > 0 else 0
    print(f"{'-'*75}")
    print(f"{'TOTAL':<45} {total_found:>10} {total_fields - total_found:>10} {overall_rate:>7.1f}%")

    total_nac = sum(len(r.get('componentes_nacionais', [])) for r in result['results'].values() if isinstance(r, dict) and 'componentes_nacionais' in r)
    total_imp = sum(len(r.get('componentes_importados', [])) for r in result['results'].values() if isinstance(r, dict) and 'componentes_importados' in r)
    total_mod = sum(len(r.get('modelos_tipos_referencias', [])) for r in result['results'].values() if isinstance(r, dict) and 'modelos_tipos_referencias' in r)

    print(f"\nComponentes Nacionais extraidos: {total_nac}")
    print(f"Componentes Importados extraidos: {total_imp}")
    print(f"Modelos/Tipos/Referencias extraidos: {total_mod}")
'''

with open(TARGET, 'w', encoding='utf-8') as f:
    f.write(CODE)

print(f"Written {len(CODE)} bytes to {TARGET}")
