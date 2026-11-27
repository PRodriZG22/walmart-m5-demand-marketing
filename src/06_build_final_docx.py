"""Paso 06: Ensamblaje automático del informe final en Word (sin modificar el .docx original)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Cm, Pt, RGBColor

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DOCS_DIR, FIGURES_DIR, METRICS_DIR, OUTPUTS_DIR  # noqa: E402

BASE_DOCX_PATH = DOCS_DIR / "Walmart informe final .docx"
REPORT_MD_PATH = OUTPUTS_DIR / "RESULTADOS_PARA_INFORME_WORD.md"
FINAL_DOCX_PATH = OUTPUTS_DIR / "Walmart_Informe_Final_COMPLETO.docx"

# Paleta corporativa Walmart
HEX_NAVY = "041E42"
HEX_BLUE = "0071CE"
HEX_ZEBRA = "F8FAFC"
HEX_BORDER = "CBD5E1"
HEX_BOX_BG = "F1F5F9"

RGB_NAVY = RGBColor(0x04, 0x1E, 0x42)
RGB_BLUE = RGBColor(0x00, 0x71, 0xCE)
RGB_DARK = RGBColor(0x1E, 0x29, 0x3B)
RGB_MUTED = RGBColor(0x47, 0x55, 0x69)
RGB_WHITE = RGBColor(0xFF, 0xFF, 0xFF)

FONT_BODY = "Cambria"
FONT_CODE = "Consolas"
USABLE_WIDTH_CM = 16.90
FIGURE_WIDTH_CM = 15.20

FIGURE_CATALOG = {
    "fig01_validation_metrics_comparison.png": (
        "Figura 1",
        "Comparativa global de error (MAE, RMSE y RMSSE) y estabilidad temporal por ventana rodante: Random Forest frente a líneas base.",
    ),
    "fig02_rmsse_store_snap_breakdown.png": (
        "Figura 2",
        "Desglose del RMSSE de Random Forest por tienda de California (CA_1–CA_4), departamento (FOODS_1–3) y días con beneficio SNAP (snap_CA).",
    ),
    "fig03_feature_importance_rf.png": (
        "Figura 3",
        "Ranking de importancia relativa de las 16 variables predictoras en el modelo operativo Random Forest final.",
    ),
    "fig04_actual_vs_forecast_examples.png": (
        "Figura 4",
        "Series reales frente a validación Ventana 4 y pronóstico operativo a 28 días (d_1942–d_1969) en tres arquetipos representativos de demanda.",
    ),
    "fig05_risk_distribution_store_dept.png": (
        "Figura 5",
        "Distribución del Ingreso en Riesgo proyectado a 28 días (USD) y conteo de SKUs por tienda, departamento y nivel de riesgo.",
    ),
    "fig06_kmeans_elbow_silhouette.png": (
        "Figura 6",
        "Validación empírica del número óptimo de clústeres (K = 2..6): Método del Codo (WCSS) y Coeficiente de Silueta.",
    ),
    "fig07_kmeans_cluster_profiles.png": (
        "Figura 7",
        "Perfiles empíricos de los 4 clústeres K-Means (centroides reales y concentración del Ingreso en Riesgo USD frente al volumen de SKUs).",
    ),
    "fig08_prescriptive_marketing_revenue_risk.png": (
        "Figura 8",
        "Cobertura de portafolio e Ingreso en Riesgo (USD) asignado a cada línea del motor prescriptivo de marketing y capa transversal SNAP.",
    ),
    "fig09_dashboard_tab1_resumen.png": (
        "Figura 9",
        "Dashboard interactivo (Pestaña 1 — Resumen Ejecutivo): KPIs de riesgo, 3 decisiones inmediatas y distribución por tienda y estrategia.",
    ),
    "fig10_dashboard_tab2_producto.png": (
        "Figura 10",
        "Dashboard interactivo (Pestaña 2 — Decisión por Producto): Tarjeta semáforo y pronóstico a 28 días para FOODS_3_282 en CA_3.",
    ),
    "fig11_dashboard_tab3_simulador.png": (
        "Figura 11",
        "Dashboard interactivo (Pestaña 3 — Simulador de Campañas): Simulación de descuentos inteligentes (20%–35%), curva de sensibilidad y plan priorizado.",
    ),
}

DASHBOARD_CAPTURE_FILES = [
    "fig09_dashboard_tab1_resumen.png",
    "fig10_dashboard_tab2_producto.png",
    "fig11_dashboard_tab3_simulador.png",
]

TEAM_MEMBERS = [
    "1. Chulluncuy Cambillo, Adolfo Milton",
    "2. Felix Delgado, Alexander",
    "3. Siccha Dávila, Angel",
    "4. Zavala Gamero, Piero Rodrigo",
]
FACULTY_FULL_LINE = (
    "Facultad de Ingeniería — Escuela Profesional de Ingeniería de Sistemas — "
    "Universidad Nacional de Cañete (UNDC)"
)

# Regex para parsear **negrita**, *cursiva* y `código` en línea
INLINE_TOKEN_RE = re.compile(r"(\*\*.*?\*\*|`[^`]+`|\*[^*\n]+\*)")

# Mapa exacto y verificado de separadores de miles con punto en Secciones 2–7
# (excluye explícitamente decimales como 0.629, 1.010, 1.065, 15.014, 18.193)
THOUSANDS_DOT_TO_COMMA = {
    "6.841.121": "6,841,121",
    "387.883": "387,883",
    "51.290": "51,290",
    "42.840": "42,840",
    "33.681": "33,681",
    "30.490": "30,490",
    "22.339": "22,339",
    "5.748": "5,748",
    "5.507": "5,507",
    "5.206": "5,206",
    "4.523": "4,523",
    "3.214": "3,214",
    "3.049": "3,049",
    "1.969": "1,969",
    "1.947": "1,947",
    "1.941": "1,941",
    "1.437": "1,437",
    "1.095": "1,095",
}
THOUSANDS_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in THOUSANDS_DOT_TO_COMMA) + r")\b"
)


def unify_thousands_in_paragraph(paragraph) -> int:
    """Reemplaza separadores de miles con punto por coma preservando formato por run."""
    count = 0
    for run in paragraph.runs:
        if run.text:
            new_text, n = THOUSANDS_RE.subn(lambda m: THOUSANDS_DOT_TO_COMMA[m.group(0)], run.text)
            if n > 0:
                run.text = new_text
                count += n
    return count


def apply_base_consistency_edits(doc: Document, ref_anchor) -> dict[str, int | bool]:
    """Aplica actualización de portada y pulidos de consistencia en Secciones 1–7 (sin tocar el original)."""
    stats: dict[str, int | bool] = {
        "cover_faculty_updated": False,
        "cover_members_updated": 0,
        "paso8_updated": False,
        "paso9_updated": False,
        "sec72_note_added": False,
        "thousands_unified_count": 0,
    }

    # 0) Portada (Sección 1): Facultad/Escuela Profesional e Integrantes
    for p in doc.paragraphs[:15]:
        t = p.text.strip()
        if t.startswith("Facultad / Escuela Profesional:"):
            p.clear()
            r_lbl = p.add_run("Facultad / Escuela Profesional: ")
            r_lbl.bold = True
            p.add_run(FACULTY_FULL_LINE)
            stats["cover_faculty_updated"] = True
        else:
            for idx_m, member_name in enumerate(TEAM_MEMBERS, start=1):
                placeholder = f"[Espacio para colocar nombre completo del Integrante {idx_m}]"
                if placeholder in t:
                    p.clear()
                    p.add_run(member_name)
                    stats["cover_members_updated"] = int(stats["cover_members_updated"]) + 1
                    break

    assert stats["cover_faculty_updated"], "No se encontró 'Facultad / Escuela Profesional:' en portada"
    assert stats["cover_members_updated"] == 4, f"Solo se actualizaron {stats['cover_members_updated']}/4 integrantes"

    # 1) Ajuste 1: Sección 6.3 (Paso 8) — hiperparámetros reales de RandomForestRegressor
    for p in doc.paragraphs:
        if p.text.strip().startswith("Paso 8 — Entrenamiento de RandomForestRegressor"):
            # Reconstruir preservando el estilo original 'List Report' y negritas clave
            p.clear()
            r_hdr = p.add_run("Paso 8 — Entrenamiento de RandomForestRegressor y Evaluación frente a 3 Líneas Base:")
            r_hdr.bold = True
            p.add_run(" En cada ventana temporal se entrena un modelo global RandomForestRegressor de scikit-learn configurado con ")
            r_hp = p.add_run(
                '100 árboles de decisión (n_estimators=100), profundidad máxima acotada (max_depth=16), '
                'mínimo de 25 observaciones por hoja (min_samples_leaf=25), submuestreo bootstrap del 30% (max_samples=0.30), '
                'selección de raíz cuadrada de predictores por división (max_features="sqrt"), '
                'paralelización controlada de 6 hilos (n_jobs=6) y semilla aleatoria fija (random_state=42)'
            )
            r_hp.bold = True
            p.add_run(
                " para garantizar estabilidad de memoria y reproducibilidad exacta [8], [10], [11]. "
                "Su precisión predictiva se compara de forma justa contra "
            )
            r_b1 = p.add_run("3 métodos base (")
            r_b1.bold = True
            r_b2 = p.add_run("baselines")
            r_b2.bold = True
            r_b2.italic = True
            r_b3 = p.add_run(") clásicos de la literatura")
            r_b3.bold = True
            p.add_run(" [1], [2], [3], [8]:")
            stats["paso8_updated"] = True
            break

    # 2) Ajuste 2: Sección 6.3 (Paso 9) — precisión exacta del enunciado de validación
    old_p9 = "Verificada la superioridad predictiva de Random Forest en las 4 ventanas de validación"
    new_p9 = (
        "Verificada la superioridad predictiva de Random Forest en RMSE global "
        "y frente a Seasonal Naïve en las 4 ventanas de validación"
    )
    for p in doc.paragraphs:
        if p.text.strip().startswith("Paso 9 —") and old_p9 in p.text:
            for run in p.runs:
                if old_p9 in run.text:
                    run.text = run.text.replace(old_p9, new_p9)
                    stats["paso9_updated"] = True
                    break
            break

    # 3) Ajuste 3: Sección 7.2 — nota metodológica enlazando los perfiles conceptuales con K=4 en Sección 8.4
    sec73_anchor = None
    for p in doc.paragraphs:
        if p.text.strip().startswith("7.3."):
            sec73_anchor = p
            break
    assert sec73_anchor is not None, "No se encontró el encabezado '7.3.' para insertar la nota de la Sección 7.2"
    p_note = sec73_anchor.insert_paragraph_before(style="Normal")
    p_note.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p_note.paragraph_format.space_before = Pt(4)
    p_note.paragraph_format.space_after = Pt(8)
    r_nl = p_note.add_run("Nota metodológica: ")
    r_nl.font.name = FONT_BODY
    r_nl.font.size = Pt(11.0)
    r_nl.bold = True
    r_nl.font.color.rgb = RGB_NAVY
    r_nt = p_note.add_run(
        "Los perfiles conceptuales descritos anteriormente constituyen la referencia operativa del diseño comercial; "
        "su partición estadística definitiva sobre las 5,748 series de California se valida empíricamente "
        "en K = 4 clústeres diferenciados en la Sección 8.4."
    )
    r_nt.font.name = FONT_BODY
    r_nt.font.size = Pt(11.0)
    r_nt.italic = True
    stats["sec72_note_added"] = True

    # 4) Ajuste 4b: Unificar separadores de miles (punto -> coma) en Secciones 2–7 (párrafos y tablas base)
    total_unified = 0
    for p in doc.paragraphs:
        if p._p is ref_anchor._p:
            break
        total_unified += unify_thousands_in_paragraph(p)

    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    total_unified += unify_thousands_in_paragraph(p)

    stats["thousands_unified_count"] = total_unified
    assert stats["paso8_updated"], "No se pudo actualizar el Paso 8 de la Sección 6.3"
    assert stats["paso9_updated"], "No se pudo actualizar el Paso 9 de la Sección 6.3"
    return stats


def is_technical_identifier(token: str) -> bool:
    """Determina si un span entre backticks debe ir en fuente monoespaciada (identificador/archivo)."""
    markers = ("_", ".csv", ".parquet", ".py", ".md", ".json", ".docx", "/", "==", ">=", "<=", "t-", "d_")
    return any(m in token for m in markers)


def add_formatted_runs(
    paragraph,
    text: str,
    font_size_pt: float = 11.0,
    base_color: RGBColor | None = None,
    force_bold: bool = False,
    force_italic: bool = False,
) -> None:
    """Agrega runs formateados interpretando **negrita**, *cursiva* y `código` sin dejar sintaxis Markdown."""
    pos = 0
    for match in INLINE_TOKEN_RE.finditer(text):
        if match.start() > pos:
            plain = text[pos : match.start()]
            run = paragraph.add_run(plain)
            run.font.name = FONT_BODY
            run.font.size = Pt(font_size_pt)
            run.bold = force_bold
            run.italic = force_italic
            if base_color is not None:
                run.font.color.rgb = base_color

        tok = match.group(0)
        if tok.startswith("**") and tok.endswith("**"):
            inner = tok[2:-2]
            # Soportar `código` o *cursiva* dentro de **negrita**
            add_formatted_runs(
                paragraph,
                inner,
                font_size_pt=font_size_pt,
                base_color=base_color,
                force_bold=True,
                force_italic=force_italic,
            )
        elif tok.startswith("`") and tok.endswith("`"):
            inner = tok[1:-1]
            run = paragraph.add_run(inner)
            if is_technical_identifier(inner):
                run.font.name = FONT_CODE
                run.font.size = Pt(max(font_size_pt - 1.5, 7.0))
            else:
                run.font.name = FONT_BODY
                run.font.size = Pt(font_size_pt)
            run.bold = force_bold
            run.italic = force_italic
            if base_color is not None:
                run.font.color.rgb = base_color
        elif tok.startswith("*") and tok.endswith("*"):
            inner = tok[1:-1]
            add_formatted_runs(
                paragraph,
                inner,
                font_size_pt=font_size_pt,
                base_color=base_color,
                force_bold=force_bold,
                force_italic=True,
            )
        pos = match.end()

    if pos < len(text):
        tail = text[pos:]
        run = paragraph.add_run(tail)
        run.font.name = FONT_BODY
        run.font.size = Pt(font_size_pt)
        run.bold = force_bold
        run.italic = force_italic
        if base_color is not None:
            run.font.color.rgb = base_color


def set_cell_shading(cell, hex_color: str) -> None:
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading)


def set_cell_margins(cell, top: int = 55, bottom: int = 55, left: int = 75, right: int = 75) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement("w:tcMar")
    for side, val in (("top", top), ("bottom", bottom), ("left", left), ("right", right)):
        node = OxmlElement(f"w:{side}")
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        tcMar.append(node)
    tcPr.append(tcMar)


def set_table_borders(table, border_hex: str = HEX_BORDER, sz: str = "4", style: str = "single") -> None:
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'  <w:top w:val="{style}" w:sz="{sz}" w:space="0" w:color="{border_hex}"/>'
        f'  <w:bottom w:val="{style}" w:sz="{sz}" w:space="0" w:color="{border_hex}"/>'
        f'  <w:left w:val="{style}" w:sz="{sz}" w:space="0" w:color="{border_hex}"/>'
        f'  <w:right w:val="{style}" w:sz="{sz}" w:space="0" w:color="{border_hex}"/>'
        f'  <w:insideH w:val="{style}" w:sz="{sz}" w:space="0" w:color="{border_hex}"/>'
        f'  <w:insideV w:val="{style}" w:sz="{sz}" w:space="0" w:color="{border_hex}"/>'
        f"</w:tblBorders>"
    )
    tblPr.append(borders)


def set_table_width_dxa(table, width_cm: float) -> None:
    dxa = int(round(width_cm / 2.54 * 1440))
    tblPr = table._tbl.tblPr
    for existing in tblPr.findall(qn("w:tblW")):
        tblPr.remove(existing)
    tblW = OxmlElement("w:tblW")
    tblW.set(qn("w:w"), str(dxa))
    tblW.set(qn("w:type"), "dxa")
    tblPr.append(tblW)


def set_row_cant_split(row) -> None:
    trPr = row._tr.get_or_add_trPr()
    trPr.append(OxmlElement("w:cantSplit"))


def set_row_header(row) -> None:
    trPr = row._tr.get_or_add_trPr()
    trPr.append(OxmlElement("w:tblHeader"))


def insert_styled_table_before(
    doc: Document,
    anchor_p,
    headers: list[str],
    aligns: list[str],
    data_rows: list[list[str]],
) -> None:
    """Crea una tabla Word corporativa (#041E42 encabezado, texto blanco, bordes sutiles) antes de anchor_p."""
    n_cols = len(headers)
    n_rows = 1 + len(data_rows)
    table = doc.add_table(rows=n_rows, cols=n_cols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    set_table_width_dxa(table, USABLE_WIDTH_CM)
    set_table_borders(table, border_hex=HEX_BORDER, sz="4", style="single")

    # Ajustar tamaño de fuente según número de columnas para evitar desbordamientos
    if n_cols >= 9:
        hdr_pt, cell_pt = 7.5, 7.5
        pad_lr = 45
    elif n_cols >= 7:
        hdr_pt, cell_pt = 8.5, 8.0
        pad_lr = 55
    elif n_cols >= 5:
        hdr_pt, cell_pt = 9.0, 8.5
        pad_lr = 65
    else:
        hdr_pt, cell_pt = 9.5, 9.0
        pad_lr = 85

    # Encabezado
    hdr_row = table.rows[0]
    set_row_header(hdr_row)
    set_row_cant_split(hdr_row)
    for c_idx, h_text in enumerate(headers):
        cell = hdr_row.cells[c_idx]
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        set_cell_shading(cell, HEX_NAVY)
        set_cell_margins(cell, top=70, bottom=70, left=pad_lr, right=pad_lr)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if aligns[c_idx] == "right" else WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        add_formatted_runs(p, h_text, font_size_pt=hdr_pt, base_color=RGB_WHITE, force_bold=True)

    # Filas de datos
    for r_idx, row_vals in enumerate(data_rows, start=1):
        row = table.rows[r_idx]
        set_row_cant_split(row)
        is_total_row = any(v.strip().startswith("**Total") for v in row_vals)
        is_rf_highlight = (headers[0].strip() == "Modelo") and ("Random Forest" in row_vals[0])
        if is_total_row:
            bg_hex = "E2E8F0"
        elif is_rf_highlight:
            bg_hex = "EFF6FF"
        else:
            bg_hex = HEX_ZEBRA if r_idx % 2 == 0 else "FFFFFF"
        for c_idx, val in enumerate(row_vals):
            cell = row.cells[c_idx]
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            set_cell_shading(cell, bg_hex)
            set_cell_margins(cell, top=50, bottom=50, left=pad_lr, right=pad_lr)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if aligns[c_idx] == "right" else WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            add_formatted_runs(
                p,
                val,
                font_size_pt=cell_pt,
                base_color=RGB_NAVY if is_rf_highlight else RGB_DARK,
                force_bold=(is_total_row or is_rf_highlight),
            )

    # Mover la tabla justo antes de anchor_p
    anchor_p._p.addprevious(table._tbl)

    # Pequeño espacio tras la tabla
    spacer = anchor_p.insert_paragraph_before("")
    spacer.paragraph_format.space_before = Pt(0)
    spacer.paragraph_format.space_after = Pt(4)


def insert_figure_before(anchor_p, filename: str) -> None:
    """Inserta una figura PNG centrada (~15.2 cm) con pie de figura numerado antes de anchor_p."""
    img_path = FIGURES_DIR / filename
    assert img_path.exists(), f"Figura no encontrada: {img_path}"
    fig_num, caption = FIGURE_CATALOG[filename]

    p_img = anchor_p.insert_paragraph_before()
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.paragraph_format.space_before = Pt(8)
    p_img.paragraph_format.space_after = Pt(3)
    p_img.paragraph_format.keep_with_next = True
    run_img = p_img.add_run()
    run_img.add_picture(str(img_path), width=Cm(FIGURE_WIDTH_CM))

    p_cap = anchor_p.insert_paragraph_before()
    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cap.paragraph_format.space_before = Pt(0)
    p_cap.paragraph_format.space_after = Pt(10)
    r_num = p_cap.add_run(f"{fig_num}. ")
    r_num.font.name = FONT_BODY
    r_num.font.size = Pt(9.5)
    r_num.bold = True
    r_num.font.color.rgb = RGB_NAVY

    r_txt = p_cap.add_run(caption)
    r_txt.font.name = FONT_BODY
    r_txt.font.size = Pt(9.5)
    r_txt.italic = True
    r_txt.font.color.rgb = RGB_MUTED


def insert_screenshot_box_before(doc: Document, anchor_p, title: str, detail: str) -> None:
    """Inserta un recuadro claramente marcado con borde azul discontinuo para pegar capturas Streamlit."""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_width_dxa(tbl, 15.6)
    set_table_borders(tbl, border_hex=HEX_BLUE, sz="12", style="dashed")

    row = tbl.rows[0]
    set_row_cant_split(row)
    cell = row.cells[0]
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    set_cell_shading(cell, HEX_BOX_BG)
    set_cell_margins(cell, top=220, bottom=220, left=200, right=200)

    p1 = cell.paragraphs[0]
    p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p1.paragraph_format.space_before = Pt(4)
    p1.paragraph_format.space_after = Pt(4)
    r1 = p1.add_run(title)
    r1.font.name = FONT_BODY
    r1.font.size = Pt(10.5)
    r1.bold = True
    r1.font.color.rgb = RGB_NAVY

    p2 = cell.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2.paragraph_format.space_before = Pt(2)
    p2.paragraph_format.space_after = Pt(6)
    add_formatted_runs(p2, detail, font_size_pt=9.5, base_color=RGB_MUTED, force_italic=True)

    p3 = cell.add_paragraph()
    p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p3.paragraph_format.space_before = Pt(8)
    p3.paragraph_format.space_after = Pt(4)
    r3 = p3.add_run("[ Pegar aquí la captura de pantalla del Dashboard Streamlit (ancho sugerido: 15 cm) ]")
    r3.font.name = FONT_BODY
    r3.font.size = Pt(9.0)
    r3.bold = True
    r3.font.color.rgb = RGB_BLUE

    anchor_p._p.addprevious(tbl._tbl)

    spacer = anchor_p.insert_paragraph_before("")
    spacer.paragraph_format.space_before = Pt(0)
    spacer.paragraph_format.space_after = Pt(6)


def parse_md_table(table_lines: list[str]) -> tuple[list[str], list[str], list[list[str]]]:
    """Convierte líneas de tabla Markdown en (headers, aligns, rows)."""
    def split_row(ln: str) -> list[str]:
        return [c.strip() for c in ln.strip().strip("|").split("|")]

    headers = split_row(table_lines[0])
    align_cells = split_row(table_lines[1])
    aligns = []
    for a in align_cells:
        if a.endswith(":") and not a.startswith(":"):
            aligns.append("right")
        elif a.startswith(":") and a.endswith(":"):
            aligns.append("center")
        else:
            aligns.append("left")
    data_rows = [split_row(ln) for ln in table_lines[2:]]
    return headers, aligns, data_rows


def extract_sections_8_and_9(md_text: str) -> list[str]:
    """Extrae estrictamente desde '## 8. Resultados Empíricos' hasta antes de '## Anexo A'."""
    lines = md_text.splitlines()
    start_idx = next(
        (i for i, ln in enumerate(lines) if ln.startswith("## 8. Resultados Empíricos")),
        None,
    )
    end_idx = next(
        (i for i, ln in enumerate(lines) if ln.startswith("## Anexo A")),
        len(lines),
    )
    assert start_idx is not None, "No se encontró '## 8. Resultados Empíricos' en el archivo Markdown"
    return lines[start_idx:end_idx]


def main() -> None:
    print("=" * 76)
    print("PASO 06 — ENSAMBLAJE FINAL DE WORD (Walmart_Informe_Final_COMPLETO.docx)")
    print("=" * 76)

    assert BASE_DOCX_PATH.exists(), f"Archivo base no encontrado: {BASE_DOCX_PATH}"
    assert REPORT_MD_PATH.exists(), f"Archivo Markdown no encontrado: {REPORT_MD_PATH}"

    doc = Document(str(BASE_DOCX_PATH))
    base_paragraphs = len(doc.paragraphs)
    base_tables = len(doc.tables)
    base_images = len(doc.inline_shapes)
    print(
        f"Base cargada: {BASE_DOCX_PATH.name} "
        f"(párrafos={base_paragraphs}, tablas={base_tables}, imágenes={base_images})"
    )

    # Localizar y renumerar '8. Referencias Bibliográficas' -> '10. Referencias Bibliográficas'
    ref_anchor = None
    for p in doc.paragraphs:
        if p.text.strip().startswith("8. Referencias Bibliográficas"):
            ref_anchor = p
            break
    assert ref_anchor is not None, "No se encontró '8. Referencias Bibliográficas' en el .docx base"

    # Renumerar preservando el estilo 'Heading 1'
    ref_anchor.text = "10. Referencias Bibliográficas"
    ref_anchor.paragraph_format.page_break_before = True
    print("  [OK] Renumerado: '8. Referencias Bibliográficas' -> '10. Referencias Bibliográficas'")

    # Aplicar los 4 ajustes de consistencia en Secciones 2–7 sobre la copia en memoria
    consistency_stats = apply_base_consistency_edits(doc, ref_anchor)
    print(
        f"  [OK] Pulido Secciones 2–7: Paso 8={consistency_stats['paso8_updated']}, "
        f"Paso 9={consistency_stats['paso9_updated']}, Nota 7.2={consistency_stats['sec72_note_added']}, "
        f"miles unificados={consistency_stats['thousands_unified_count']}"
    )

    # Parsear Secciones 8 y 9 del Markdown (excluyendo Anexo A y Anexo B)
    md_text = REPORT_MD_PATH.read_text(encoding="utf-8")
    sec_lines = extract_sections_8_and_9(md_text)

    inserted_tables = 0
    inserted_figures = 0
    inserted_boxes = 0

    # Contenedor de recuadros de capturas Streamlit en 8.5
    screenshot_specs = [
        (
            "RECUADRO DE CAPTURA 1 — Dashboard Streamlit: Tab 1 (Resumen Ejecutivo y Riesgo Comercial)",
            "Incluir los 5 indicadores KPI dinámicos, la alerta de concentración del Clúster C3 (72.7% del riesgo en 11.4% de SKUs), el gráfico de barras por tienda (CA_1–CA_4) y el Treemap de estrategia.",
        ),
        (
            "RECUADRO DE CAPTURA 2 — Dashboard Streamlit: Tab 2 (Explorador de Pronóstico RF vs. Real)",
            "Seleccionar `FOODS_3_282_CA_3_evaluation` (Riesgo Alto, Cross-Selling) o `FOODS_3_587_CA_1_evaluation` (Markdown) mostrando 90 días reales, Ventana 4, pronóstico 28d, franjas amarillas SNAP y ficha prescriptiva.",
        ),
        (
            "RECUADRO DE CAPTURA 3 — Dashboard Streamlit: Tab 4 (Simulador Markdown 20%–35% y Plan de Promociones)",
            "Mostrar el simulador interactivo en escenario Base (d = 25%, ε = 0.6), la curva de sensibilidad, la alerta operativa LEFO→FEFO / stockpiling (-20% a -30%) y la tabla filtrable exportable a CSV.",
        ),
    ]
    screenshot_idx = 0

    i = 0
    n_lines = len(sec_lines)
    while i < n_lines:
        ln = sec_lines[i].strip()

        # Ignorar líneas vacías y separadores horizontales Markdown ---
        if not ln or ln == "---":
            i += 1
            continue

        # Encabezados de nivel 1 (## 8. ... / ## 9. ...)
        if ln.startswith("## "):
            heading_txt = ln[3:].strip()
            p = ref_anchor.insert_paragraph_before(heading_txt, style="Heading 1")
            if heading_txt.startswith("8."):
                p.paragraph_format.page_break_before = True
            i += 1
            continue

        # Encabezados de nivel 2 (### 8.1. ... / ### 9.1. ...)
        if ln.startswith("### "):
            heading_txt = ln[4:].strip().replace("`", "")
            ref_anchor.insert_paragraph_before(heading_txt, style="Heading 2")
            i += 1
            continue

        # Tablas Markdown nativas
        if ln.startswith("|") and ln.endswith("|"):
            tbl_lines = []
            while i < n_lines and sec_lines[i].strip().startswith("|") and sec_lines[i].strip().endswith("|"):
                tbl_lines.append(sec_lines[i].strip())
                i += 1
            headers, aligns, data_rows = parse_md_table(tbl_lines)
            # Ajuste 4a: en Tabla 8.2, ubicar Random Forest en primera fila para lectura comparativa directa
            if headers and headers[0].strip() == "Modelo":
                rf_rows = [r for r in data_rows if "Random Forest" in r[0]]
                other_rows = [r for r in data_rows if "Random Forest" not in r[0]]
                data_rows = rf_rows + other_rows
            insert_styled_table_before(doc, ref_anchor, headers, aligns, data_rows)
            inserted_tables += 1
            continue

        # Bloques citados (>) que indican inserción de figuras o espacios de capturas del dashboard
        if ln.startswith(">"):
            block_lines = []
            while i < n_lines and sec_lines[i].strip().startswith(">"):
                block_lines.append(sec_lines[i].strip().lstrip(">").strip())
                i += 1
            joined = " ".join(block_lines)

            # Detectar referencias a fig01..fig08 e insertar las imágenes reales
            found_figs = re.findall(r"(fig0[1-8]_[a-z0-9_]+\.png)", joined)
            for fname in found_figs:
                insert_figure_before(ref_anchor, fname)
                inserted_figures += 1

            # Detectar marcadores de capturas de dashboard Streamlit -> incrustar fig09, fig10 y fig11 reales
            if "Espacio reservado para Captura" in joined:
                n_caps = joined.count("Espacio reservado para Captura")
                for _ in range(n_caps):
                    if screenshot_idx < len(DASHBOARD_CAPTURE_FILES):
                        insert_figure_before(ref_anchor, DASHBOARD_CAPTURE_FILES[screenshot_idx])
                        screenshot_idx += 1
                        inserted_figures += 1
            continue

        # Títulos de tabla (**Tabla 8.X.** ...)
        if ln.startswith("**Tabla "):
            p = ref_anchor.insert_paragraph_before(style="Normal")
            p.paragraph_format.space_before = Pt(8)
            p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.keep_with_next = True
            add_formatted_runs(p, ln, font_size_pt=10.0, base_color=RGB_NAVY)
            i += 1
            continue

        # Listas con viñetas (- ...)
        if ln.startswith("- "):
            bullet_txt = ln[2:].strip()
            p = ref_anchor.insert_paragraph_before(style="Normal")
            p.paragraph_format.left_indent = Cm(0.75)
            p.paragraph_format.first_line_indent = Cm(-0.35)
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(4)
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            r_bul = p.add_run("•  ")
            r_bul.font.name = FONT_BODY
            r_bul.font.size = Pt(11.0)
            r_bul.bold = True
            r_bul.font.color.rgb = RGB_BLUE
            add_formatted_runs(p, bullet_txt, font_size_pt=11.0)
            i += 1
            continue

        # Listas numeradas (1. ..., 2. ..., etc.)
        m_num = re.match(r"^(\d+)\.\s+(.*)$", ln)
        if m_num:
            num_str, item_txt = m_num.group(1), m_num.group(2).strip()
            p = ref_anchor.insert_paragraph_before(style="Normal")
            p.paragraph_format.left_indent = Cm(0.75)
            p.paragraph_format.first_line_indent = Cm(-0.45)
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(5)
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            r_n = p.add_run(f"{num_str}. ")
            r_n.font.name = FONT_BODY
            r_n.font.size = Pt(11.0)
            r_n.bold = True
            r_n.font.color.rgb = RGB_NAVY
            add_formatted_runs(p, item_txt, font_size_pt=11.0)
            i += 1
            continue

        # Párrafo normal académico justificado (alineando cualquier mención de Tab 4 -> Pestaña 3)
        ln_clean = ln.replace("Tab 4", "Pestaña 3").replace("Tab 1", "Pestaña 1").replace("Tab 2", "Pestaña 2")
        p = ref_anchor.insert_paragraph_before(style="Normal")
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(6)
        add_formatted_runs(p, ln_clean, font_size_pt=11.0)
        i += 1

    # Guardar copia nueva sin tocar el archivo original
    doc.save(str(FINAL_DOCX_PATH))

    # Verificación integral reabriendo el .docx generado con python-docx
    verify_doc = Document(str(FINAL_DOCX_PATH))
    final_paragraphs = len(verify_doc.paragraphs)
    final_tables = len(verify_doc.tables)
    final_images = len(verify_doc.inline_shapes)
    size_mb = round(FINAL_DOCX_PATH.stat().st_size / (1024 * 1024), 2)

    # Verificar encabezados clave en orden correcto
    headings = [p.text.strip() for p in verify_doc.paragraphs if p.style.name == "Heading 1"]
    assert any(h.startswith("8. Resultados Empíricos") for h in headings), "Falta Heading 1 de Sección 8"
    assert any(h.startswith("9. Conclusiones y Recomendaciones") for h in headings), "Falta Heading 1 de Sección 9"
    assert any(h.startswith("10. Referencias Bibliográficas") for h in headings), "Falta Heading 1 de Sección 10"
    assert not any(h.startswith("8. Referencias") for h in headings), "Quedó encabezado '8. Referencias' sin renumerar"

    # Verificar ausencia del Anexo B (diapositivas PDF) y presencia de las 11 figuras (fig01..fig11)
    full_text = "\n".join(p.text for p in verify_doc.paragraphs)
    assert "Tabla de Actualización para Diapositivas PDF" not in full_text, "Se coló el Anexo B en el Word"
    assert "RECUADRO DE CAPTURA" not in full_text, "Quedó un recuadro vacío de captura"
    assert inserted_figures == 11, f"Se esperaban 11 figuras insertadas (fig01..fig11), obtenidas {inserted_figures}"
    assert inserted_boxes == 0, f"Se esperaban 0 recuadros vacíos, obtenidos {inserted_boxes}"

    # Verificar ecuaciones nativas m:oMath preservadas intactas
    import zipfile
    import xml.etree.ElementTree as ET

    with zipfile.ZipFile(str(FINAL_DOCX_PATH)) as zf:
        xml_root = ET.fromstring(zf.read("word/document.xml"))
    omath_count = len(xml_root.findall(".//{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath"))
    assert omath_count >= 127, f"Se esperaban >=127 ecuaciones nativas m:oMath, halladas {omath_count}"

    audit = {
        "status": "PASS",
        "base_docx": str(BASE_DOCX_PATH),
        "output_docx": str(FINAL_DOCX_PATH),
        "output_size_mb": size_mb,
        "native_omath_equations_preserved": omath_count,
        "base_counts": {
            "paragraphs": base_paragraphs,
            "tables": base_tables,
            "inline_images": base_images,
        },
        "inserted_counts": {
            "empirical_data_tables": inserted_tables,
            "screenshot_placeholder_boxes": inserted_boxes,
            "figures_embedded": inserted_figures,
        },
        "final_verified_counts": {
            "paragraphs": final_paragraphs,
            "tables_total": final_tables,
            "inline_images": final_images,
        },
        "base_consistency_edits": consistency_stats,
        "heading_1_outline": headings,
    }
    audit_path = METRICS_DIR / "final_docx_audit.json"
    with audit_path.open("w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2, ensure_ascii=False)

    print("\n--- RESUMEN DE VERIFICACIÓN (reabierto con python-docx) ---")
    print(f"  - Archivo generado            : {FINAL_DOCX_PATH} ({size_mb:.2f} MB)")
    print(f"  - Archivo original preservado : {BASE_DOCX_PATH} (intacto)")
    print(f"  - Portada actualizada         : Facultad={consistency_stats['cover_faculty_updated']}, Integrantes={consistency_stats['cover_members_updated']}/4")
    print(f"  - Ecuaciones nativas m:oMath  : {omath_count} preservadas intactas")
    print(f"  - Párrafos totales            : {base_paragraphs} -> {final_paragraphs}")
    print(f"  - Tablas totales en Word      : {base_tables} base + {inserted_tables} empíricas = {final_tables}")
    print(f"  - Imágenes embebidas          : {base_images} -> {final_images} (fig01..fig11 a {FIGURE_WIDTH_CM:.1f} cm)")
    print("  - Índice Heading 1 final      :")
    for h in headings:
        print(f"      * {h}")
    print("=" * 76)
    print(f"PASO 06 COMPLETADO: PASS -> {audit_path}")
    print("=" * 76)


if __name__ == "__main__":
    main()
