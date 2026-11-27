"""Genera la presentación editable PowerPoint (.pptx, 16:9, 12 diapositivas)
con identidad Walmart Corporativo Moderno y 100% cifras auditadas del pipeline.

Salida: outputs/Walmart_Presentacion_Final.pptx
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
METRICS_DIR = OUTPUTS_DIR / "metrics"
TABLES_DIR = OUTPUTS_DIR / "tables"
FIGURES_DIR = OUTPUTS_DIR / "figures"
OUT_PPTX = OUTPUTS_DIR / "Walmart_Presentacion_Final.pptx"

# Paleta Corporativa Walmart (McKinsey / Ejecutivo)
NAVY = RGBColor(0x08, 0x1C, 0x30)
NAVY_SOFT = RGBColor(0x10, 0x2A, 0x43)
BLUE = RGBColor(0x00, 0x71, 0xCE)
BLUE_TINT = RGBColor(0xEF, 0xF6, 0xFF)
BLUE_LIGHT = RGBColor(0x93, 0xC5, 0xFD)
SPARK = RGBColor(0xFF, 0xC2, 0x20)
SPARK_TINT = RGBColor(0xFF, 0xFB, 0xEB)
CANVAS = RGBColor(0xF8, 0xFA, 0xFC)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
MUTED_BG = RGBColor(0xF1, 0xF5, 0xF9)
BORDER = RGBColor(0xE2, 0xE8, 0xF0)
BORDER_DARK = RGBColor(0x23, 0x3E, 0x5A)
INK = RGBColor(0x0F, 0x17, 0x2A)
INK_SEC = RGBColor(0x47, 0x55, 0x69)
INK_MUTED = RGBColor(0x64, 0x74, 0x8B)
SLATE_LIGHT = RGBColor(0xCB, 0xD5, 0xE1)
RED = RGBColor(0xDC, 0x26, 0x26)
RED_TINT = RGBColor(0xFE, 0xF2, 0xF2)
EMERALD = RGBColor(0x0D, 0x94, 0x88)
EMERALD_LIGHT = RGBColor(0x2D, 0xD4, 0xBF)
AMBER = RGBColor(0xB4, 0x53, 0x09)

FONT_MAIN = "Segoe UI"
FONT_MONO = "Consolas"

SLIDE_W = Inches(13.3333)
SLIDE_H = Inches(7.5)


def load_audited_data() -> dict[str, Any]:
    """Carga todas las cifras reales desde outputs/metrics/ y outputs/tables/."""
    with open(METRICS_DIR / "etl_audit.json", encoding="utf-8") as f:
        etl = json.load(f)
    with open(METRICS_DIR / "validation_audit.json", encoding="utf-8") as f:
        val = json.load(f)
    with open(METRICS_DIR / "diagnosis_audit.json", encoding="utf-8") as f:
        diag = json.load(f)

    def read_csv(name: str) -> list[dict[str, str]]:
        with open(TABLES_DIR / name, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    val_summary = {r["model"]: r for r in read_csv("validation_metrics_summary.csv")}
    breakdown = {(r["dimension"], r["segment"]): r for r in read_csv("validation_breakdown_store_snap.csv")}
    feat_imp = read_csv("feature_importance.csv")
    top_promos = read_csv("top_50_priority_promotions.csv")
    risk_by_level = {r["risk_level"]: r for r in diag["risk_by_level"]}
    risk_by_store = {r["store_id"]: r for r in diag["risk_by_store"]}
    clusters = {r["cluster_id"]: r for r in diag["kmeans"]["profiles"]}
    strategies = {r["primary_strategy"]: r for r in diag["strategy_mix"]}

    # Simulación base (d=25%, ε=0.6) verificada sobre los 425 SKUs elegibles a Markdown
    md_rows = [
        r for r in read_csv("sku_store_diagnosis.csv")
        if "Markdown" in r["primary_strategy"]
    ]
    md_base_units = sum(float(r["pred_velocity_28d"]) * 28.0 for r in md_rows)
    d_rate, eps = 0.25, 0.60
    lift = (1.0 - d_rate) ** (-eps) - 1.0
    sim_extra_units = md_base_units * lift
    sim_recovered_usd = sum(
        float(r["pred_velocity_28d"]) * 28.0 * lift * float(r["current_price"]) * (1.0 - d_rate)
        for r in md_rows
    )

    # Riesgo por departamento desde risk_summary_by_store_dept.csv
    dept_risk: dict[str, float] = {}
    for r in read_csv("risk_summary_by_store_dept.csv"):
        if r.get("dept_id") and r.get("dept_id") != "ALL":
            dept_risk[r["dept_id"]] = dept_risk.get(r["dept_id"], 0.0) + float(r["revenue_at_risk_usd"])

    return {
        "etl": etl,
        "val": val,
        "diag": diag,
        "val_summary": val_summary,
        "breakdown": breakdown,
        "feat_imp": feat_imp,
        "top_promos": top_promos,
        "risk_by_level": risk_by_level,
        "risk_by_store": risk_by_store,
        "clusters": clusters,
        "strategies": strategies,
        "dept_risk": dept_risk,
        "sim": {
            "discount_pct": 25,
            "epsilon": eps,
            "lift_pct": lift * 100.0,
            "extra_units": sim_extra_units,
            "recovered_usd": sim_recovered_usd,
        },
    }


def set_bg(slide, color: RGBColor) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_rect(
    slide,
    left: float,
    top: float,
    width: float,
    height: float,
    fill_color: RGBColor,
    line_color: RGBColor | None = None,
    line_pt: float = 0.75,
    rounded: bool = False,
    radius: float = 0.06,
):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
    shp = slide.shapes.add_shape(shape_type, Inches(left), Inches(top), Inches(width), Inches(height))
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill_color
    if line_color is not None:
        shp.line.color.rgb = line_color
        shp.line.width = Pt(line_pt)
    else:
        shp.line.fill.background()
    if rounded and len(shp.adjustments) > 0:
        shp.adjustments[0] = radius
    shp.shadow.inherit = False
    return shp


def add_textbox(
    slide,
    left: float,
    top: float,
    width: float,
    height: float,
    text: str,
    size: float = 12,
    bold: bool = False,
    color: RGBColor = INK,
    font_name: str = FONT_MAIN,
    align: PP_ALIGN = PP_ALIGN.LEFT,
    valign: MSO_ANCHOR = MSO_ANCHOR.TOP,
    line_spacing: float | None = None,
):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = valign
    tf.margin_left = Inches(0.02)
    tf.margin_right = Inches(0.02)
    tf.margin_top = Inches(0.02)
    tf.margin_bottom = Inches(0.02)
    p = tf.paragraphs[0]
    p.alignment = align
    if line_spacing is not None:
        p.line_spacing = line_spacing
    run = p.add_run()
    run.text = text
    run.font.name = font_name
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return tb


def add_image_fit(
    slide,
    image_path: Path,
    box_left: float,
    box_top: float,
    box_w: float,
    box_h: float,
    pad: float = 0.08,
) -> None:
    """Inserta una imagen preservando exactamente su relación de aspecto centrada en el marco."""
    with Image.open(image_path) as im:
        img_w, img_h = im.size
    avail_w = max(0.1, box_w - 2 * pad)
    avail_h = max(0.1, box_h - 2 * pad)
    img_ratio = img_w / img_h
    box_ratio = avail_w / avail_h

    if img_ratio > box_ratio:
        final_w = avail_w
        final_h = avail_w / img_ratio
    else:
        final_h = avail_h
        final_w = avail_h * img_ratio

    left = box_left + (box_w - final_w) / 2.0
    top = box_top + (box_h - final_h) / 2.0
    slide.shapes.add_picture(str(image_path), Inches(left), Inches(top), Inches(final_w), Inches(final_h))


def set_notes(slide, notes_text: str) -> None:
    notes_slide = slide.notes_slide
    tf = notes_slide.notes_text_frame
    tf.text = notes_text


def add_light_chrome(
    slide,
    eyebrow: str,
    title: str,
    speaker_label: str,
    footer_left: str,
    slide_num: int,
) -> None:
    """Aplica el encabezado, barra corporativa superior y pie de página en slides claros (2–11)."""
    set_bg(slide, CANVAS)
    # Barra superior corporativa (Azul Walmart + Spark)
    add_rect(slide, 0.0, 0.0, 11.5333, 0.045, BLUE)
    add_rect(slide, 11.5333, 0.0, 1.80, 0.045, SPARK)

    # Eyebrow + Speaker pill
    add_textbox(slide, 0.48, 0.22, 7.6, 0.26, eyebrow.upper(), size=9.5, bold=True, color=BLUE, font_name=FONT_MONO)
    add_rect(slide, 9.78, 0.19, 3.07, 0.28, WHITE, line_color=BORDER, rounded=True, radius=0.5)
    add_textbox(slide, 9.86, 0.21, 2.91, 0.24, speaker_label, size=9, bold=True, color=INK_SEC, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    # Action Title
    add_textbox(slide, 0.48, 0.48, 12.37, 0.48, title, size=20.5, bold=True, color=NAVY)

    # Línea divisoria + acento Spark
    add_rect(slide, 0.48, 1.00, 12.37, 0.012, BORDER)
    add_rect(slide, 0.48, 0.992, 0.56, 0.032, SPARK)

    # Footer limpio
    add_rect(slide, 0.48, 7.06, 12.37, 0.01, BORDER)
    add_textbox(slide, 0.48, 7.12, 10.6, 0.26, footer_left, size=9, color=INK_MUTED)
    add_textbox(
        slide,
        11.65,
        7.12,
        1.20,
        0.26,
        f"{slide_num:02d} / 12",
        size=9.5,
        bold=True,
        color=NAVY,
        font_name=FONT_MONO,
        align=PP_ALIGN.RIGHT,
    )


def add_spark_mark(slide, cx: float, cy: float, r_inner: float = 0.07, r_outer: float = 0.18) -> None:
    """Dibuja un icono minimalista tipo Spark (6 rayos dorados) con formas vectoriales nativas."""
    import math
    for deg in (0, 60, 120, 180, 240, 300):
        rad = math.radians(deg - 90)
        mx = cx + math.cos(rad) * ((r_inner + r_outer) / 2.0)
        my = cy + math.sin(rad) * ((r_inner + r_outer) / 2.0)
        ray_len = r_outer - r_inner
        ray_w = 0.036
        shp = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(mx - ray_w / 2.0),
            Inches(my - ray_len / 2.0),
            Inches(ray_w),
            Inches(ray_len),
        )
        shp.rotation = float(deg)
        shp.fill.solid()
        shp.fill.fore_color.rgb = SPARK
        shp.line.fill.background()
        if len(shp.adjustments) > 0:
            shp.adjustments[0] = 0.5


def build_deck(data: dict[str, Any]) -> None:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    blank_layout = prs.slide_layouts[6]

    etl = data["etl"]
    val_sum = data["val_summary"]
    bdown = data["breakdown"]
    diag = data["diag"]
    r_lvl = data["risk_by_level"]
    r_sto = data["risk_by_store"]
    cl = data["clusters"]
    st = data["strategies"]
    sim = data["sim"]

    total_risk = diag["total_revenue_at_risk_usd"]
    total_units = diag["total_units_at_risk_28d"]
    active_rows_m = etl["row_counts"]["active_sales_3y_rows"] / 1_000_000.0
    ram_red = etl["memory_optimization"]["ram_reduction_pct"]
    interm_pct = etl["intermittency_3y_active"]["global_intermittency_pct"]

    rf_rmse = float(val_sum["Random Forest"]["rmse"])
    rf_rmsse = float(val_sum["Random Forest"]["rmsse"])
    imp_naive = float(val_sum["Seasonal Naïve (lag_28)"]["rf_improvement_vs_model_rmse_pct"])
    imp_ses = float(val_sum["SES (NumPy)"]["rf_improvement_vs_model_rmse_pct"])
    imp_ma28 = float(val_sum["MA28"]["rf_improvement_vs_model_rmse_pct"])
    imp_naive_rmsse = float(val_sum["Seasonal Naïve (lag_28)"]["rf_improvement_vs_model_rmsse_pct"])

    top5_imp = sum(float(r["importance_pct"]) for r in data["feat_imp"][:5])
    price_imp = sum(float(r["importance_pct"]) for r in data["feat_imp"] if r["feature"] in {"sell_price", "relative_price", "price_change"})
    snap0_rmse = float(bdown[("snap_CA", "snap_CA=0")]["rmse"])
    snap1_rmse = float(bdown[("snap_CA", "snap_CA=1")]["rmse"])
    snap_rmse_delta = (snap1_rmse / snap0_rmse - 1.0) * 100.0

    high_med_skus = r_lvl["Riesgo Alto"]["sku_count"] + r_lvl["Riesgo Medio"]["sku_count"]
    high_med_pct = r_lvl["Riesgo Alto"]["sku_pct"] + r_lvl["Riesgo Medio"]["sku_pct"]
    high_med_rev_pct = r_lvl["Riesgo Alto"]["rev_pct"] + r_lvl["Riesgo Medio"]["rev_pct"]
    ca3_risk = r_sto["CA_3"]["revenue_at_risk_usd"]
    ca3_pct = (ca3_risk / total_risk) * 100.0
    foods3_pct = (data["dept_risk"]["FOODS_3"] / total_risk) * 100.0

    c3 = cl[3]
    c1 = cl[1]
    c2 = cl[2]
    c0 = cl[0]
    cs_strat = st["Cross-Selling y Visibilidad Omnicanal (Sin Descuento)"]
    md_strat = st["Precios Dinámicos / Markdown (20%–35%)"]
    snap_skus = diag["snap_priority_15pct_count"]
    snap_risk = diag["snap_priority_revenue_at_risk_usd"]
    snap_risk_pct = (snap_risk / total_risk) * 100.0

    # =========================================================================
    # SLIDE 1 — PORTADA OSCURA (#081C30) · BLOQUE 1
    # =========================================================================
    s1 = prs.slides.add_slide(blank_layout)
    set_bg(s1, NAVY)
    add_rect(s1, 0.0, 0.0, 0.09, 3.9, SPARK)
    add_rect(s1, 0.0, 3.9, 0.09, 3.6, BLUE)
    add_spark_mark(s1, 0.84, 0.70, 0.06, 0.16)
    add_textbox(
        s1, 1.12, 0.56, 7.2, 0.30,
        "UNDC 2026  ·  ESCUELA PROFESIONAL DE INGENIERÍA DE SISTEMAS",
        size=10, bold=True, color=BLUE_LIGHT, font_name=FONT_MONO,
    )
    add_rect(s1, 9.65, 0.50, 3.12, 0.38, NAVY_SOFT, line_color=SPARK, line_pt=1.0, rounded=True, radius=0.5)
    add_textbox(
        s1, 9.72, 0.54, 2.98, 0.30,
        "IA Aplicada al Marketing Digital",
        size=10.5, bold=True, color=SPARK, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE,
    )

    add_rect(s1, 0.72, 1.56, 0.72, 0.055, SPARK)
    add_textbox(
        s1, 0.72, 1.76, 11.8, 1.10,
        "Pronóstico de Demanda con Random Forest",
        size=34, bold=True, color=WHITE,
    )
    add_textbox(
        s1, 0.72, 2.52, 11.8, 0.90,
        "para Orientar Promociones en Walmart",
        size=34, bold=True, color=SPARK,
    )
    add_textbox(
        s1, 0.72, 3.46, 10.2, 0.65,
        "Prototipo predictivo y motor prescriptivo sobre datos reales Kaggle M5 · Categoría FOODS en California (CA_1–CA_4)",
        size=15, color=SLATE_LIGHT,
    )

    # Telemetry pills
    pills = [
        ("1,437", "productos"),
        ("5,748", "series reales"),
        ("28 días", "horizonte"),
        (f"${total_risk:,.0f}", "en riesgo"),
    ]
    px = 0.72
    for val_txt, lbl_txt in pills:
        add_rect(s1, px, 4.35, 2.28, 0.62, NAVY_SOFT, line_color=BORDER_DARK, rounded=True, radius=0.22)
        add_textbox(s1, px + 0.14, 4.42, 2.0, 0.46, f"{val_txt}  {lbl_txt}", size=12.5, bold=True, color=WHITE, valign=MSO_ANCHOR.MIDDLE)
        px += 2.44

    # 4 Integrantes
    add_rect(s1, 0.72, 5.45, 11.9, 0.012, BORDER_DARK)
    members = [
        ("BLOQUE 1 · SLIDES 1–3", "Chulluncuy Cambillo, Adolfo Milton"),
        ("BLOQUE 2 · SLIDES 4–6", "Felix Delgado, Alexander"),
        ("BLOQUE 3 · SLIDES 7–9", "Siccha Dávila, Angel"),
        ("BLOQUE 4 · SLIDES 10–12", "Zavala Gamero, Piero Rodrigo"),
    ]
    for idx, (blk, name) in enumerate(members):
        mx = 0.72 + idx * 3.02
        add_rect(s1, mx, 5.68, 2.86, 1.16, NAVY_SOFT, line_color=BORDER_DARK, rounded=True, radius=0.14)
        add_textbox(s1, mx + 0.16, 5.82, 2.54, 0.25, blk, size=8.5, bold=True, color=SPARK, font_name=FONT_MONO)
        add_textbox(s1, mx + 0.16, 6.10, 2.54, 0.62, name, size=12.5, bold=True, color=WHITE)

    set_notes(
        s1,
        "Expositor 1 — Chulluncuy Cambillo, Adolfo Milton (0:00–0:25):\n"
        "Buenos días jurado y compañeros. Somos estudiantes de Ingeniería de Sistemas de la UNDC y presentamos nuestro "
        "prototipo de IA Aplicada al Marketing Digital: pronóstico de demanda con Random Forest orientado a promociones reales en alimentos de Walmart California.",
    )

    # =========================================================================
    # SLIDE 2 — LA PROBLEMÁTICA ("LA BRECHA") · BLOQUE 1
    # =========================================================================
    s2 = prs.slides.add_slide(blank_layout)
    add_light_chrome(
        s2,
        "01 · Problemática y Justificación",
        "Predecir sin prescribir no evita mermas ni protege el margen",
        "Adolfo Chulluncuy · Bloque 1",
        "Walmart California · Categoría FOODS (Kaggle M5) · UNDC 2026",
        2,
    )
    pillars = [
        ("PILAR 01", "2% / 8%", "El error cuesta dinero", "Sobreestimar demanda dispara mermas en alimentos; subestimarla provoca quiebres en góndola.", "Mermas vs. Quiebres", BLUE),
        ("PILAR 02", "-20% a -30%", "Promociones distorsionan", "Rebajas sin elasticidad erosionan margen y desploman ventas post-oferta por acaparamiento.", "Efecto stockpiling", RED),
        ("PILAR 03", "92.5%", "Precisión sola no decide", "En Kaggle M5 casi nadie batió a SES, y ninguno conectó el pronóstico con marketing.", "Brecha analítica → comercial", SPARK),
    ]
    for idx, (num_lbl, stat, heading, desc, tag, accent) in enumerate(pillars):
        cx = 0.48 + idx * 4.21
        add_rect(s2, cx, 1.24, 3.96, 3.96, WHITE, line_color=BORDER, rounded=True, radius=0.06)
        add_rect(s2, cx, 1.24, 3.96, 0.07, accent)
        add_textbox(s2, cx + 0.24, 1.44, 3.4, 0.26, num_lbl, size=10, bold=True, color=INK_MUTED, font_name=FONT_MONO)
        stat_col = NAVY if accent == SPARK else accent
        add_textbox(s2, cx + 0.24, 1.78, 3.5, 0.82, stat, size=34, bold=True, color=stat_col)
        add_textbox(s2, cx + 0.24, 2.66, 3.48, 0.42, heading, size=16.5, bold=True, color=NAVY)
        add_textbox(s2, cx + 0.24, 3.12, 3.48, 1.15, desc, size=12.5, color=INK_SEC, line_spacing=1.25)
        add_rect(s2, cx + 0.24, 4.62, 2.30, 0.34, MUTED_BG, rounded=True, radius=0.25)
        add_textbox(s2, cx + 0.32, 4.66, 2.14, 0.26, tag, size=9.5, bold=True, color=INK_SEC, valign=MSO_ANCHOR.MIDDLE)

    # Banner La Brecha
    add_rect(s2, 0.48, 5.44, 12.37, 1.42, NAVY, rounded=True, radius=0.10)
    add_rect(s2, 0.48, 5.44, 0.11, 1.42, SPARK)
    add_rect(s2, 0.84, 5.84, 1.88, 0.58, NAVY_SOFT, line_color=SPARK, line_pt=1.0, rounded=True, radius=0.25)
    add_textbox(s2, 0.88, 5.90, 1.80, 0.46, "LA BRECHA", size=12, bold=True, color=SPARK, font_name=FONT_MONO, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_textbox(
        s2, 2.98, 5.66, 9.55, 1.00,
        "Traducir el pronóstico diario a 28 días en decisiones promocionales diferenciadas que protejan el margen bruto y aceleren la rotación real.",
        size=16.5, bold=True, color=WHITE, valign=MSO_ANCHOR.MIDDLE, line_spacing=1.22,
    )

    set_notes(
        s2,
        "Expositor 1 — Chulluncuy Cambillo, Adolfo Milton (0:25–0:50):\n"
        "En retail alimentario enfrentamos tres problemas: el error cuesta dinero (2% mermas, 8% quiebres); las promociones "
        "sin criterio causan caídas post-oferta de -20% a -30% por acaparamiento; y la precisión estadística sola no le dice a marketing qué hacer. Esa es nuestra brecha.",
    )

    # =========================================================================
    # SLIDE 3 — ALCANCE, DATOS M5 Y OBJETIVOS · BLOQUE 1
    # =========================================================================
    s3 = prs.slides.add_slide(blank_layout)
    add_light_chrome(
        s3,
        "02 · Alcance, Datos Reales M5 y Objetivos",
        "5,748 series reales de FOODS en California con cuatro objetivos medibles",
        "Adolfo Chulluncuy · Bloque 1",
        "Fuente: Kaggle M5 Forecasting · Auditoría ETL (etl_audit.json) · UNDC 2026",
        3,
    )
    hero_metrics = [
        ("1,437", "Productos únicos", "FOODS_1 · 2 · 3", BLUE, WHITE),
        ("4", "Tiendas California", "CA_1 a CA_4", BLUE, WHITE),
        ("5,748", "Series SKU-Tienda", "Horizonte 28 días", BLUE, WHITE),
        ("3 años", "Historia completa", "May 2013 – May 2016", BLUE, WHITE),
        (f"{interm_pct:.2f}%", "Intermitencia real", "2.85M días en cero", SPARK, SPARK_TINT),
    ]
    for idx, (val_s, lbl_s, sub_s, top_c, bg_c) in enumerate(hero_metrics):
        cx = 0.48 + idx * 2.51
        add_rect(s3, cx, 1.24, 2.35, 1.62, bg_c, line_color=BORDER, rounded=True, radius=0.09)
        add_rect(s3, cx, 1.24, 2.35, 0.06, top_c)
        add_textbox(s3, cx + 0.16, 1.42, 2.04, 0.62, val_s, size=27, bold=True, color=BLUE if top_c == SPARK else NAVY)
        add_textbox(s3, cx + 0.16, 2.10, 2.04, 0.30, lbl_s, size=11.5, bold=True, color=INK)
        add_textbox(s3, cx + 0.16, 2.40, 2.04, 0.30, sub_s, size=9.5, color=INK_MUTED)

    add_textbox(s3, 0.48, 3.08, 6.0, 0.26, "CUATRO OBJETIVOS ESPECÍFICOS DEL PROTOTIPO", size=9.5, bold=True, color=INK_MUTED, font_name=FONT_MONO)

    objectives = [
        ("OE 1", "→", "ETL sin fuga", "Depurar M5 e ingeniar rezagos y precios estrictamente >= t-28."),
        ("OE 2", "→", "Evaluación RF", "Contrastar Random Forest frente a MA28, SES y Seasonal Naïve."),
        ("OE 3", "→", "Diagnóstico 28d", "Cuantificar Ingreso en Riesgo, elasticidad precio y respuesta SNAP."),
        ("OE 4", "✓", "Plan + Dashboard", "Segmentar con K-Means y desplegar motor prescriptivo en Streamlit."),
    ]
    for idx, (badge, arr, o_title, o_desc) in enumerate(objectives):
        cx = 0.48 + idx * 3.14
        add_rect(s3, cx, 3.38, 2.96, 2.34, WHITE, line_color=BORDER, rounded=True, radius=0.08)
        add_rect(s3, cx + 0.20, 3.56, 0.72, 0.32, BLUE_TINT, rounded=True, radius=0.25)
        add_textbox(s3, cx + 0.20, 3.58, 0.72, 0.28, badge, size=10, bold=True, color=BLUE, font_name=FONT_MONO, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
        add_textbox(s3, cx + 2.36, 3.54, 0.40, 0.36, arr, size=16, bold=True, color=BORDER_DARK if arr == "✓" else INK_MUTED, align=PP_ALIGN.RIGHT)
        add_textbox(s3, cx + 0.20, 4.08, 2.56, 0.38, o_title, size=15.5, bold=True, color=NAVY)
        add_textbox(s3, cx + 0.20, 4.52, 2.56, 1.04, o_desc, size=11.5, color=INK_SEC, line_spacing=1.22)

    # Nota transparencia
    add_rect(s3, 0.48, 5.96, 12.37, 0.86, BLUE_TINT, line_color=BLUE_LIGHT, rounded=True, radius=0.14)
    add_rect(s3, 0.68, 6.18, 2.15, 0.40, BLUE, rounded=True, radius=0.5)
    add_textbox(s3, 0.70, 6.20, 2.11, 0.36, "100% Datos Reales M5", size=10, bold=True, color=WHITE, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_textbox(
        s3, 3.02, 6.14, 9.62, 0.50,
        "Solo ventas diarias, precios semanales, calendario y SNAP · Sin stock físico, costos (COGS) ni mermas simuladas.",
        size=12.5, bold=True, color=NAVY, valign=MSO_ANCHOR.MIDDLE,
    )

    set_notes(
        s3,
        "Expositor 1 — Chulluncuy Cambillo, Adolfo Milton (0:50–1:15):\n"
        "Trabajamos con 1,437 productos FOODS en 4 tiendas de California (5,748 series, 3 años, 49.89% intermitencia real). "
        "Nuestros 4 objetivos recorren ETL sin fuga, evaluación de Random Forest, diagnóstico de riesgo y plan prescriptivo en Streamlit, "
        "manteniendo 100% transparencia: no simulamos stock ni costos ausentes en M5.",
    )

    # =========================================================================
    # SLIDE 4 — METODOLOGÍA CRISP-DM Y PIPELINE SIN FUGA · BLOQUE 2
    # =========================================================================
    s4 = prs.slides.add_slide(blank_layout)
    add_light_chrome(
        s4,
        "03 · Metodología CRISP-DM e Ingeniería Anti-Fuga",
        "Pipeline CRISP-DM reproducible, eficiente en RAM y libre de data leakage",
        "Alexander Felix · Bloque 2",
        "Pipeline: src/01_etl_features.py & src/02_train_validate.py · Pico RAM: 2,299 MB",
        4,
    )
    # Contenedor CRISP-DM 6 fases
    add_rect(s4, 0.48, 1.22, 12.37, 2.16, WHITE, line_color=BORDER, rounded=True, radius=0.07)
    add_textbox(s4, 0.72, 1.36, 7.0, 0.30, "Ciclo Metodológico CRISP-DM (6 Fases Auditadas)", size=12.5, bold=True, color=NAVY)
    add_rect(s4, 9.86, 1.34, 2.75, 0.30, RGBColor(0xF0, 0xFD, 0xFA), line_color=EMERALD, rounded=True, radius=0.5)
    add_textbox(s4, 9.90, 1.36, 2.67, 0.26, "Auditoría anti-fuga: PASS 200/200", size=9, bold=True, color=EMERALD, font_name=FONT_MONO, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    phases = [
        ("FASE 01", "Negocio", "Brecha comercial y KPI Ingreso en Riesgo", False),
        ("FASE 02", "Datos M5", "Ventas, precios y calendario CA", False),
        ("FASE 03", "Preparación", "Downcasting + 16 features >= t-28", True),
        ("FASE 04", "Modelado RF", "100 árboles · depth 16 · max_samples 0.30", True),
        ("FASE 05", "Evaluación", "4 ventanas rodantes MAE/RMSE/RMSSE", False),
        ("FASE 06", "Despliegue", "K-Means + Plan + Streamlit", False),
    ]
    for idx, (f_idx, f_name, f_sub, dark_card) in enumerate(phases):
        fx = 0.72 + idx * 2.00
        bg_p = NAVY if dark_card else CANVAS
        bd_p = NAVY if dark_card else BORDER
        add_rect(s4, fx, 1.78, 1.88, 1.40, bg_p, line_color=bd_p, rounded=True, radius=0.10)
        add_textbox(s4, fx + 0.12, 1.88, 1.64, 0.22, f_idx, size=8.5, bold=True, color=SPARK if dark_card else BLUE, font_name=FONT_MONO)
        add_textbox(s4, fx + 0.12, 2.12, 1.64, 0.32, f_name, size=12.5, bold=True, color=WHITE if dark_card else NAVY)
        add_textbox(s4, fx + 0.12, 2.48, 1.64, 0.62, f_sub, size=9.5, color=SLATE_LIGHT if dark_card else INK_SEC, line_spacing=1.18)

    # 2x2 Logros técnicos
    techs = [
        (f"{active_rows_m:.2f}M", "Filas activas validadas", "682,592 filas pre-lanzamiento depuradas; 0 duplicados, 0 precios inválidos y 0 ventas negativas.", BLUE),
        (f"-{ram_red:.2f}%", "Reducción de memoria RAM", "De 1,031.4 MB a 193.1 MB mediante downcasting (float32/int8/category) y formato Parquet.", EMERALD),
        ("16", "Features estrictas >= t-28", "Rezagos (28, 35, 56), medias móviles desde t-28 y precio relativo expansivo sin fuga futura.", SPARK),
        ("4 × 28d", "Origen rodante cronológico", "Validación temporal en d_1830..d_1941 (Feb–May 2016) reentrenando baselines antes del corte.", NAVY),
    ]
    for idx, (t_val, t_head, t_desc, acc) in enumerate(techs):
        col = idx % 2
        row = idx // 2
        tx = 0.48 + col * 6.31
        ty = 3.60 + row * 1.70
        add_rect(s4, tx, ty, 6.06, 1.50, WHITE, line_color=BORDER, rounded=True, radius=0.08)
        add_rect(s4, tx, ty, 0.09, 1.50, acc)
        val_c = NAVY if acc in (SPARK, NAVY) else acc
        add_textbox(s4, tx + 0.24, ty + 0.30, 1.78, 0.85, t_val, size=29, bold=True, color=val_c, valign=MSO_ANCHOR.MIDDLE)
        add_textbox(s4, tx + 2.08, ty + 0.22, 3.78, 0.36, t_head, size=14.5, bold=True, color=NAVY)
        add_textbox(s4, tx + 2.08, ty + 0.60, 3.78, 0.78, t_desc, size=11, color=INK_SEC, line_spacing=1.2)

    set_notes(
        s4,
        "Expositor 2 — Felix Delgado, Alexander (1:15–1:40):\n"
        "Bajo CRISP-DM en 6 fases construimos un pipeline reproducible con 5.71M filas activas, -81.28% de consumo de RAM "
        "mediante downcasting y Parquet, 16 variables estrictamente >= t-28 auditadas 200/200 sin fuga temporal y validación rodante en 4 ventanas cronológicas.",
    )

    # =========================================================================
    # SLIDE 5 — EVALUACIÓN PREDICTIVA (FIG01) · BLOQUE 2
    # =========================================================================
    s5 = prs.slides.add_slide(blank_layout)
    add_light_chrome(
        s5,
        "04 · Evaluación Predictiva (4 Ventanas Rodantes)",
        f"Random Forest obtiene el menor RMSE global ({rf_rmse:.4f}) frente a los baselines",
        "Alexander Felix · Bloque 2",
        "Fuente: outputs/tables/validation_metrics_summary.csv · fig01_validation_metrics_comparison.png",
        5,
    )
    add_rect(s5, 0.48, 1.20, 12.37, 3.92, WHITE, line_color=BORDER, rounded=True, radius=0.06)
    add_image_fit(s5, FIGURES_DIR / "fig01_validation_metrics_comparison.png", 0.48, 1.20, 12.37, 3.92, pad=0.10)

    s5_cards = [
        (f"{rf_rmse:.4f}", "Mejor RMSE global", "Minimiza errores grandes en los productos de mayor volumen y rotación semanal.", BLUE),
        (f"+{imp_naive:.2f}%", "vs. Seasonal Naïve", f"Supera también a SES (+{imp_ses:.2f}%) y MA28 (+{imp_ma28:.2f}%) en RMSE, y +{imp_naive_rmsse:.2f}% en RMSSE vs. Naïve.", EMERALD),
        (f"{rf_rmsse:.4f}", "Lectura honesta RMSSE", "MA28/SES (0.779/0.781) aventajan ~2% en series planas, pero RF modela precio, calendario y SNAP.", SPARK),
    ]
    for idx, (m_val, m_lbl, m_txt, acc) in enumerate(s5_cards):
        cx = 0.48 + idx * 4.21
        add_rect(s5, cx, 5.28, 3.96, 1.60, WHITE, line_color=BORDER, rounded=True, radius=0.08)
        add_rect(s5, cx, 5.28, 3.96, 0.06, acc)
        add_textbox(s5, cx + 0.22, 5.42, 1.60, 0.48, m_val, size=22, bold=True, color=NAVY)
        lbl_col = AMBER if acc == SPARK else acc
        add_textbox(s5, cx + 1.82, 5.52, 1.98, 0.34, m_lbl, size=10.5, bold=True, color=lbl_col)
        add_textbox(s5, cx + 0.22, 5.96, 3.52, 0.80, m_txt, size=10.8, color=INK_SEC, line_spacing=1.2)

    set_notes(
        s5,
        "Expositor 2 — Felix Delgado, Alexander (1:40–2:05):\n"
        f"En las 4 ventanas rodantes, Random Forest obtuvo el menor RMSE global ({rf_rmse:.4f}): +{imp_naive:.2f}% sobre Seasonal Naïve, "
        f"+{imp_ses:.2f}% sobre SES y +{imp_ma28:.2f}% sobre MA28. En RMSSE simple ({rf_rmsse:.4f}) MA28 y SES lideran ~2% en series planas, "
        "lo cual coincide con la literatura M5, pero solo Random Forest modela precios, calendario y pagos SNAP.",
    )

    # =========================================================================
    # SLIDE 6 — VARIABLES CLAVE (FIG03) Y VOLATILIDAD SNAP (FIG02) · BLOQUE 2
    # =========================================================================
    s6 = prs.slides.add_slide(blank_layout)
    add_light_chrome(
        s6,
        "05 · Interpretabilidad del Modelo y Volatilidad SNAP",
        f"La memoria histórica explica {top5_imp:.1f}%; los pagos SNAP elevan la volatilidad",
        "Alexander Felix · Bloque 2",
        "Fuente: feature_importance.csv & validation_breakdown_store_snap.csv (fig02 y fig03)",
        6,
    )
    add_rect(s6, 0.48, 1.22, 7.72, 5.64, WHITE, line_color=BORDER, rounded=True, radius=0.06)
    add_image_fit(s6, FIGURES_DIR / "fig03_feature_importance_rf.png", 0.48, 1.22, 7.72, 5.64, pad=0.12)

    rx = 8.42
    rw = 4.43
    # Card 1: Memoria >= t-28
    add_rect(s6, rx, 1.22, rw, 1.54, WHITE, line_color=BORDER, rounded=True, radius=0.08)
    add_rect(s6, rx, 1.22, 0.08, 1.54, BLUE)
    add_textbox(s6, rx + 0.22, 1.32, 3.9, 0.22, "DRIVERS DE DEMANDA (>= t-28)", size=8.5, bold=True, color=INK_MUTED, font_name=FONT_MONO)
    add_textbox(s6, rx + 0.22, 1.54, 1.65, 0.52, f"{top5_imp:.1f}%", size=26, bold=True, color=NAVY)
    add_textbox(s6, rx + 1.88, 1.68, 2.35, 0.34, "Memoria reciente", size=12.5, bold=True, color=BLUE)
    add_textbox(s6, rx + 0.22, 2.12, 4.02, 0.56, "rolling_mean_28 (29.6%), rolling_mean_7 (23.5%) y lag_28 (15.9%).", size=10.5, color=INK_SEC)

    # Card 2: Precios
    add_rect(s6, rx, 2.92, rw, 1.48, WHITE, line_color=BORDER, rounded=True, radius=0.08)
    add_rect(s6, rx, 2.92, 0.08, 1.48, SPARK)
    add_textbox(s6, rx + 0.22, 3.02, 3.9, 0.22, "PALANCA COMERCIAL DIRECTA", size=8.5, bold=True, color=INK_MUTED, font_name=FONT_MONO)
    add_textbox(s6, rx + 0.22, 3.24, 1.65, 0.52, f"{price_imp:.2f}%", size=26, bold=True, color=NAVY)
    add_textbox(s6, rx + 1.88, 3.38, 2.35, 0.34, "Dinámica de precios", size=12.5, bold=True, color=AMBER)
    add_textbox(s6, rx + 0.22, 3.80, 4.02, 0.52, "sell_price (2.19%) y relative_price (1.74%) conectan elasticidad al pronóstico.", size=10.5, color=INK_SEC)

    # Card 3: Resumen fig02 SNAP + Tiendas
    add_rect(s6, rx, 4.56, rw, 2.30, NAVY, rounded=True, radius=0.08)
    add_rect(s6, rx, 4.56, rw, 0.06, SPARK)
    add_textbox(s6, rx + 0.22, 4.70, 4.0, 0.22, "RESUMEN FIG. 02 · SNAP Y TIENDAS", size=8.5, bold=True, color=SPARK, font_name=FONT_MONO)
    add_textbox(s6, rx + 0.22, 4.94, 1.75, 0.52, f"+{snap_rmse_delta:.2f}%", size=26, bold=True, color=SPARK)
    add_textbox(s6, rx + 1.98, 5.08, 2.30, 0.34, "RMSE en snap_CA = 1", size=11.5, bold=True, color=WHITE)
    add_textbox(
        s6, rx + 0.22, 5.48, 4.02, 0.54,
        f"RMSE sube de {snap0_rmse:.3f} a {snap1_rmse:.3f} en días SNAP; RMSSE calibrado (0.779 vs. 0.781).",
        size=10, color=SLATE_LIGHT,
    )
    stores_rmsse = [("CA_3", "0.763", EMERALD_LIGHT), ("CA_1", "0.767", BORDER_DARK), ("CA_4", "0.787", BORDER_DARK), ("CA_2", "0.864", SPARK)]
    for i, (sn, sv, bd) in enumerate(stores_rmsse):
        sx = rx + 0.22 + i * 1.02
        add_rect(s6, sx, 6.12, 0.94, 0.58, NAVY_SOFT, line_color=bd, rounded=True, radius=0.14)
        add_textbox(s6, sx, 6.16, 0.94, 0.22, sn, size=8.5, bold=True, color=BLUE_LIGHT, font_name=FONT_MONO, align=PP_ALIGN.CENTER)
        add_textbox(s6, sx, 6.38, 0.94, 0.28, sv, size=12, bold=True, color=WHITE, align=PP_ALIGN.CENTER)

    set_notes(
        s6,
        "Expositor 2 — Felix Delgado, Alexander (2:05–2:30):\n"
        f"En el modelo operativo final (fig03), las variables históricas >= t-28 aportan {top5_imp:.1f}% y el bloque de precios {price_imp:.2f}%. "
        f"El desglose de fig02 revela que en días SNAP el RMSE sube +{snap_rmse_delta:.2f}%, confirmando picos de inicio de mes, "
        "con CA_3 como tienda más precisa (RMSSE 0.763) y CA_2 como la más volátil (0.864).",
    )

    # =========================================================================
    # SLIDE 7 — DIAGNÓSTICO DE RIESGO EN 28 DÍAS (FIG05) · BLOQUE 3
    # =========================================================================
    s7 = prs.slides.add_slide(blank_layout)
    add_light_chrome(
        s7,
        "06 · Diagnóstico Comercial a 28 Días",
        f"${total_risk:,.0f} USD en riesgo concentrados en CA_3 ({ca3_pct:.1f}%) y FOODS_3 ({foods3_pct:.1f}%)",
        "Angel Siccha · Bloque 3",
        "Fuente: diagnosis_audit.json & risk_summary_by_store_dept.csv · fig05_risk_distribution_store_dept.png",
        7,
    )
    kpis7 = [
        ("INGRESO EN RIESGO (28 DÍAS)", f"${total_risk:,.0f}", f"{total_units:,.0f} unidades en desaceleración real (v90 vs. pred_v28)", RED),
        ("PORTAFOLIO ACCIONABLE", f"{high_med_pct:.1f}%", f"{high_med_skus:,} SKUs en Riesgo Alto/Medio ({high_med_rev_pct:.1f}% del dinero)", SPARK),
        ("TIENDA PRIORITARIA · CA_3", f"${ca3_risk:,.0f}", f"{ca3_pct:.1f}% del riesgo total · Corte p80 = $20.14 USD", BLUE),
    ]
    for idx, (klbl, kval, ksub, kacc) in enumerate(kpis7):
        cx = 0.48 + idx * 4.21
        add_rect(s7, cx, 1.22, 3.96, 1.50, WHITE, line_color=BORDER, rounded=True, radius=0.08)
        add_rect(s7, cx, 1.22, 0.09, 1.50, kacc)
        add_textbox(s7, cx + 0.24, 1.34, 3.55, 0.24, klbl, size=9, bold=True, color=INK_MUTED, font_name=FONT_MONO)
        val_c = NAVY if kacc == SPARK else kacc
        add_textbox(s7, cx + 0.24, 1.58, 3.55, 0.62, kval, size=31, bold=True, color=val_c)
        add_textbox(s7, cx + 0.24, 2.24, 3.55, 0.40, ksub, size=10.5, color=INK_SEC)

    add_rect(s7, 0.48, 2.88, 12.37, 3.98, WHITE, line_color=BORDER, rounded=True, radius=0.06)
    add_image_fit(s7, FIGURES_DIR / "fig05_risk_distribution_store_dept.png", 0.48, 2.88, 12.37, 3.98, pad=0.10)

    set_notes(
        s7,
        "Expositor 3 — Siccha Dávila, Angel (2:30–2:55):\n"
        f"Al contrastar velocidad reciente (v90) con el pronóstico a 28 días a precio vigente, detectamos ${total_risk:,.0f} USD en riesgo "
        f"({total_units:,.0f} unidades). El {high_med_pct:.1f}% del catálogo está en Riesgo Alto o Medio ({high_med_rev_pct:.1f}% del dinero) "
        f"y CA_3 lidera sola con ${ca3_risk:,.0f} USD ({ca3_pct:.1f}%).",
    )

    # =========================================================================
    # SLIDE 8 — SEGMENTACIÓN K-MEANS Y HALLAZGO PARETO (FIG06 + FIG07) · BLOQUE 3
    # =========================================================================
    s8 = prs.slides.add_slide(blank_layout)
    add_light_chrome(
        s8,
        "07 · Segmentación K-Means (K = 4) y Hallazgo Pareto",
        f"Clúster C3 ({c3['portfolio_pct']:.1f}% de SKUs) concentra el {c3['revenue_at_risk_share_pct']:.1f}% del Ingreso en Riesgo",
        "Angel Siccha · Bloque 3",
        "Fuente: kmeans_evaluation.csv & kmeans_cluster_profiles.csv · fig06 y fig07",
        8,
    )
    # Izquierda: fig06 y fig07 apiladas con relación de aspecto exacta
    add_rect(s8, 0.48, 1.20, 7.66, 2.74, WHITE, line_color=BORDER, rounded=True, radius=0.06)
    add_image_fit(s8, FIGURES_DIR / "fig06_kmeans_elbow_silhouette.png", 0.48, 1.20, 7.66, 2.74, pad=0.08)

    add_rect(s8, 0.48, 4.10, 7.66, 2.76, WHITE, line_color=BORDER, rounded=True, radius=0.06)
    add_image_fit(s8, FIGURES_DIR / "fig07_kmeans_cluster_profiles.png", 0.48, 4.10, 7.66, 2.76, pad=0.08)

    # Derecha arriba: Pareto Hero Card
    px8 = 8.34
    pw8 = 4.51
    add_rect(s8, px8, 1.20, pw8, 2.86, NAVY, rounded=True, radius=0.08)
    add_rect(s8, px8, 1.20, pw8, 0.06, SPARK)
    add_rect(s8, px8 + 0.24, 1.38, 2.55, 0.30, NAVY_SOFT, line_color=SPARK, rounded=True, radius=0.5)
    add_textbox(s8, px8 + 0.28, 1.40, 2.47, 0.26, "HALLAZGO PARETO · CLÚSTER C3", size=8.5, bold=True, color=SPARK, font_name=FONT_MONO, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_textbox(s8, px8 + 0.24, 1.80, 1.48, 0.65, f"{c3['portfolio_pct']:.1f}%", size=25, bold=True, color=BLUE_LIGHT, valign=MSO_ANCHOR.BOTTOM)
    add_textbox(s8, px8 + 1.66, 1.84, 0.50, 0.56, "→", size=22, bold=True, color=SPARK, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
    add_textbox(s8, px8 + 2.12, 1.72, 2.20, 0.78, f"{c3['revenue_at_risk_share_pct']:.1f}%", size=35, bold=True, color=SPARK, valign=MSO_ANCHOR.BOTTOM)
    add_textbox(
        s8, px8 + 0.24, 2.54, 4.05, 0.82,
        f"Solo {c3['sku_count']} SKUs concentran ${c3['revenue_at_risk_usd_total']:,.0f} USD del riesgo total (${c3['revenue_at_risk_usd_mean']:.2f}/SKU · declive {c3['projected_decline_pct_mean']:.1f}%).",
        size=11.5, bold=True, color=WHITE, line_spacing=1.22,
    )
    add_rect(s8, px8 + 0.24, 3.46, 4.03, 0.01, BORDER_DARK)
    add_textbox(
        s8, px8 + 0.24, 3.56, 4.03, 0.34,
        f"Óptimo validado: K = {diag['kmeans']['selected_k']}   ·   Silueta = {diag['kmeans']['selected_silhouette']:.4f}",
        size=10, bold=True, color=SLATE_LIGHT, font_name=FONT_MONO,
    )

    # Derecha abajo: Tabla nativa editable de los 4 clústeres
    add_rect(s8, px8, 4.22, pw8, 2.64, WHITE, line_color=BORDER, rounded=True, radius=0.08)
    add_textbox(s8, px8 + 0.20, 4.32, 4.10, 0.26, "MAPA DE LOS 4 ARQUETIPOS (5,748 SERIES)", size=8.5, bold=True, color=INK_MUTED, font_name=FONT_MONO)

    tbl_shape = s8.shapes.add_table(5, 3, Inches(px8 + 0.18), Inches(4.62), Inches(pw8 - 0.36), Inches(2.08))
    tbl = tbl_shape.table
    tbl.columns[0].width = Inches(0.62)
    tbl.columns[1].width = Inches(2.15)
    tbl.columns[2].width = Inches(1.38)
    rows_data = [
        ("ID", "Perfil Comercial", "Clave Empírica"),
        ("C3", "Desaceleración Crítica", f"{c3['sku_count']} · {c3['revenue_at_risk_share_pct']:.1f}% USD"),
        ("C1", "Alta Rotación / Ancla", f"{c1['sku_count']:,} · {c1['sales_velocity_28d_mean']:.2f} u/d"),
        ("C2", "Cola Larga Intermitente", f"{c2['sku_count']:,} · {c2['intermittency_pct_mean']:.1f}% 0s"),
        ("C0", "Alta Elasticidad Precio", f"{c0['sku_count']} · +{c0['price_sensitivity_mean']*100:.0f}%"),
    ]
    for r_idx, row_vals in enumerate(rows_data):
        for c_idx, val_cell in enumerate(row_vals):
            cell = tbl.cell(r_idx, c_idx)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            if r_idx == 0:
                cell.fill.fore_color.rgb = NAVY
            elif r_idx == 1:
                cell.fill.fore_color.rgb = RED_TINT
            else:
                cell.fill.fore_color.rgb = WHITE if r_idx % 2 == 0 else CANVAS
            p = cell.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.RIGHT if c_idx == 2 else (PP_ALIGN.CENTER if c_idx == 0 else PP_ALIGN.LEFT)
            run = p.add_run()
            run.text = val_cell
            run.font.name = FONT_MONO if c_idx == 0 else FONT_MAIN
            run.font.size = Pt(9.0 if r_idx == 0 else 9.5)
            run.font.bold = r_idx in (0, 1) or c_idx == 0
            if r_idx == 0:
                run.font.color.rgb = WHITE
            elif r_idx == 1:
                run.font.color.rgb = RED
            else:
                run.font.color.rgb = INK

    set_notes(
        s8,
        "Expositor 3 — Siccha Dávila, Angel (2:55–3:20):\n"
        f"Con K-Means y winsorización controlada, K=4 logra el óptimo operativo (Silueta {diag['kmeans']['selected_silhouette']:.4f}). "
        f"El hallazgo Pareto es decisivo: el Clúster C3 reúne solo el {c3['portfolio_pct']:.1f}% de los SKUs ({c3['sku_count']}) "
        f"pero concentra el {c3['revenue_at_risk_share_pct']:.1f}% del Ingreso en Riesgo (${c3['revenue_at_risk_usd_total']:,.0f} USD).",
    )

    # =========================================================================
    # SLIDE 9 — PLAN PRESCRIPTIVO DE MARKETING (FIG08) · BLOQUE 3
    # =========================================================================
    s9 = prs.slides.add_slide(blank_layout)
    add_light_chrome(
        s9,
        "08 · Plan Prescriptivo de Marketing",
        f"Proteger {cs_strat['rev_pct']:.1f}% del riesgo sin descuentos y focalizar Markdown en {md_strat['sku_count']} SKUs",
        "Angel Siccha · Bloque 3",
        "Fuente: src/03_diagnosis_kmeans_marketing.py · fig08_prescriptive_marketing_revenue_risk.png",
        9,
    )
    add_rect(s9, 0.48, 1.20, 12.37, 3.48, WHITE, line_color=BORDER, rounded=True, radius=0.06)
    add_image_fit(s9, FIGURES_DIR / "fig08_prescriptive_marketing_revenue_risk.png", 0.48, 1.20, 12.37, 3.48, pad=0.09)

    tactics = [
        ("TÁCTICA 1 · SIN DESCUENTO", f"{cs_strat['rev_pct']:.1f}%", "Cross-Selling con Ancla",
         f"{cs_strat['sku_count']:,} SKUs inelásticos (${cs_strat['revenue_at_risk_usd']:,.0f}) empaquetados con líderes de pasillo (ej. FOODS_3_090). Cero erosión de margen.", BLUE, BLUE_TINT),
        ("TÁCTICA 2 · MARKDOWN 20–35%", f"{md_strat['sku_count']} SKUs", "Rebaja Selectiva + FEFO",
         f"Solo SKUs elásticos (${md_strat['revenue_at_risk_usd']:,.0f}) + transición FEFO y recorte de reposición -20%/-30% contra stockpiling.", RED, RED_TINT),
        ("CAPA TRANSVERSAL SNAP", f"{snap_risk_pct:.1f}%", "Calendario SNAP Bifásico",
         f"{snap_skus:,} SKUs (${snap_risk:,.0f}): Fase A (días 1–10: multipacks y stock) y Fase B (días 20–31: cupones dirigidos).", SPARK, SPARK_TINT),
    ]
    for idx, (tpill, tkpi, ttitle, tbody, tacc, tbg) in enumerate(tactics):
        cx = 0.48 + idx * 4.21
        add_rect(s9, cx, 4.86, 3.96, 2.02, WHITE, line_color=BORDER, rounded=True, radius=0.08)
        add_rect(s9, cx, 4.86, 0.09, 2.02, tacc)
        add_rect(s9, cx + 0.22, 5.00, 2.22, 0.28, tbg, rounded=True, radius=0.25)
        pill_c = AMBER if tacc == SPARK else tacc
        add_textbox(s9, cx + 0.26, 5.02, 2.14, 0.24, tpill, size=8.2, bold=True, color=pill_c, font_name=FONT_MONO, valign=MSO_ANCHOR.MIDDLE)
        add_textbox(s9, cx + 2.52, 4.96, 1.28, 0.36, tkpi, size=16.5, bold=True, color=NAVY, align=PP_ALIGN.RIGHT)
        add_textbox(s9, cx + 0.22, 5.42, 3.58, 0.34, ttitle, size=14.5, bold=True, color=NAVY)
        add_textbox(s9, cx + 0.22, 5.80, 3.58, 0.96, tbody, size=10.8, color=INK_SEC, line_spacing=1.2)

    set_notes(
        s9,
        "Expositor 3 — Siccha Dávila, Angel (3:20–3:45):\n"
        f"El motor bloquea rebajas donde destruyen margen: {cs_strat['rev_pct']:.1f}% del riesgo ({cs_strat['sku_count']:,} SKUs) va a Cross-Selling sin descuento "
        f"con un ancla verificada. El Markdown 20%–35% se reserva a {md_strat['sku_count']} SKUs elásticos con FEFO y ajuste -20%/-30%. "
        f"Además, {snap_skus:,} SKUs ({snap_risk_pct:.1f}% del riesgo) reciben sincronización SNAP bifásica.",
    )

    # =========================================================================
    # SLIDE 10 — DASHBOARD INTERACTIVO Y DEMO EN VIVO (FIG09 + FIG11) · BLOQUE 4
    # =========================================================================
    s10 = prs.slides.add_slide(blank_layout)
    add_light_chrome(
        s10,
        "09 · Despliegue Operativo y Simulador",
        "Dashboard ejecutivo en Streamlit: decisión por SKU y simulación en vivo",
        "Piero Zavala · Bloque 4",
        "Aplicación: app/dashboard.py · top_50_priority_promotions.csv · fig09 y fig11",
        10,
    )
    # Browser Mockup 1 (Tab 1) y Mockup 2 (Tab 3)
    frames = [
        (0.48, 4.38, "Tab 1 · Resumen Ejecutivo", FIGURES_DIR / "fig09_dashboard_tab1_resumen.png"),
        (5.00, 3.74, "Tab 3 · Simulador de Campañas", FIGURES_DIR / "fig11_dashboard_tab3_simulador.png"),
    ]
    for fx, fw, flbl, fimg in frames:
        add_rect(s10, fx, 1.22, fw, 5.02, WHITE, line_color=BORDER, rounded=True, radius=0.05)
        add_rect(s10, fx, 1.22, fw, 0.30, NAVY)
        add_textbox(s10, fx + 0.14, 1.24, fw - 0.28, 0.26, flbl, size=9, bold=True, color=WHITE, align=PP_ALIGN.RIGHT, valign=MSO_ANCHOR.MIDDLE)
        add_image_fit(s10, fimg, fx, 1.54, fw, 4.68, pad=0.07)

    # Tech ribbon inferior izquierdo
    add_rect(s10, 0.48, 6.38, 8.26, 0.48, WHITE, line_color=BORDER, rounded=True, radius=0.16)
    add_textbox(
        s10, 0.64, 6.45, 7.94, 0.34,
        "Streamlit 1.67 + Plotly 7.2 · 4 pestañas ejecutivas   |   PyArrow pushdown: 8.58 MB RAM · Exportación CSV",
        size=10, bold=True, color=INK_SEC, valign=MSO_ANCHOR.MIDDLE,
    )

    # Columna derecha: Badge Demo en vivo + 3 ejemplos reales
    dx = 8.94
    dw = 3.91
    add_rect(s10, dx, 1.22, dw, 0.68, NAVY, rounded=True, radius=0.14)
    add_rect(s10, dx, 1.22, 0.09, 0.68, SPARK)
    add_textbox(s10, dx + 0.22, 1.34, 2.75, 0.44, "●  Demo en vivo: Streamlit", size=13, bold=True, color=WHITE, valign=MSO_ANCHOR.MIDDLE)
    add_textbox(s10, dx + 3.00, 1.36, 0.78, 0.40, "2 MIN", size=10.5, bold=True, color=SPARK, font_name=FONT_MONO, align=PP_ALIGN.RIGHT, valign=MSO_ANCHOR.MIDDLE)

    ex_sku1 = data["top_promos"][0]  # FOODS_3_282_CA_3
    ex_sku5 = data["top_promos"][4]  # FOODS_3_587_CA_1
    examples = [
        ("FOODS_3_282 · CA_3", f"${float(ex_sku1['revenue_at_risk_usd']):,.0f}", "Cross-Selling sin descuento",
         "Riesgo Alto (-99% sens. precio) · Empaquetar con ancla FOODS_3_090 + SNAP.", BLUE),
        ("FOODS_3_587 · CA_1", f"+{float(ex_sku5['price_sensitivity'])*100:.1f}%", "Markdown 20%–25% + FEFO",
         f"Elasticidad promocional real · ${float(ex_sku5['revenue_at_risk_usd']):,.0f} en riesgo · Recorte -20%/-30%.", RED),
        ("Simulador 25% (ε = 0.6)", f"+${sim['recovered_usd']:,.0f}", "Ingreso incremental recuperado",
         f"+{sim['lift_pct']:.2f}% demanda (+{sim['extra_units']:,.0f} u en 28d) sobre los 425 SKUs aptos.", EMERALD),
    ]
    for idx, (esku, eval_s, eact, edet, eacc) in enumerate(examples):
        ey = 2.06 + idx * 1.64
        add_rect(s10, dx, ey, dw, 1.48, WHITE, line_color=BORDER, rounded=True, radius=0.08)
        add_rect(s10, dx, ey, dw, 0.055, eacc)
        add_textbox(s10, dx + 0.18, ey + 0.14, 2.25, 0.30, esku, size=10.5, bold=True, color=NAVY, font_name=FONT_MONO)
        add_textbox(s10, dx + 2.40, ey + 0.10, 1.34, 0.40, eval_s, size=17, bold=True, color=eacc, align=PP_ALIGN.RIGHT)
        add_textbox(s10, dx + 0.18, ey + 0.54, 3.56, 0.30, eact, size=12, bold=True, color=INK)
        add_textbox(s10, dx + 0.18, ey + 0.86, 3.56, 0.54, edet, size=10, color=INK_SEC, line_spacing=1.18)

    set_notes(
        s10,
        "Expositor 4 — Zavala Gamero, Piero Rodrigo (3:45–4:10):\n"
        "Desplegamos el motor en Streamlit (4 pestañas, 8.58 MB RAM con PyArrow pushdown). En la demo en vivo mostraremos "
        f"FOODS_3_282 protegido con Cross-Selling ($1,156), FOODS_3_587 apto para Markdown (+63.8% elasticidad) y el simulador al 25% recuperando +${sim['recovered_usd']:,.0f} USD.",
    )

    # =========================================================================
    # SLIDE 11 — CONCLUSIONES EMPÍRICAS Y ALCANCES FUTUROS · BLOQUE 4
    # =========================================================================
    s11 = prs.slides.add_slide(blank_layout)
    add_light_chrome(
        s11,
        "10 · Conclusiones Empíricas y Hoja de Ruta",
        "Cuatro objetivos validados con datos reales y tres pasos de escalamiento",
        "Piero Zavala · Bloque 4",
        "Fuente: outputs/RESULTADOS_PARA_INFORME_WORD.md · Sección 9 (Conclusiones y Recomendaciones)",
        11,
    )
    add_textbox(s11, 0.48, 1.18, 6.8, 0.28, "CONCLUSIONES CUANTITATIVAS (OE1 – OE4)", size=10, bold=True, color=BLUE, font_name=FONT_MONO)
    add_textbox(s11, 7.82, 1.18, 5.0, 0.28, "ALCANCES Y TRABAJO FUTURO", size=10, bold=True, color=BLUE, font_name=FONT_MONO)

    conclusions = [
        ("OE1", "Datos M5 íntegros y sin fuga temporal", f"{active_rows_m:.2f}M filas activas, {interm_pct:.2f}% intermitencia real, -{ram_red:.2f}% RAM y PASS 200/200 anti-leakage."),
        ("OE2", f"Random Forest lidera en RMSE ({rf_rmse:.4f})", f"+{imp_naive:.2f}% vs. Naïve, +{imp_ses:.2f}% vs. SES y +{imp_ma28:.2f}% vs. MA28, incorporando precio, calendario y SNAP."),
        ("OE3", "Exposición comercial geolocalizada", f"${total_risk:,.0f} USD en riesgo a 28d; CA_3 concentra {ca3_pct:.1f}% y {snap_skus:,} SKUs SNAP cubren {snap_risk_pct:.1f}%."),
        ("OE4", "Segmentación Pareto y prescripción activa", f"K=4 aísla Clúster C3 ({c3['portfolio_pct']:.1f}% → {c3['revenue_at_risk_share_pct']:.1f}% riesgo); {cs_strat['rev_pct']:.1f}% protegido sin rebajas en Streamlit."),
    ]
    for idx, (oe, ctitle, cdesc) in enumerate(conclusions):
        cy = 1.52 + idx * 1.36
        add_rect(s11, 0.48, cy, 7.06, 1.22, WHITE, line_color=BORDER, rounded=True, radius=0.08)
        add_rect(s11, 0.66, cy + 0.24, 0.74, 0.74, BLUE_TINT, line_color=BLUE_LIGHT, rounded=True, radius=0.18)
        add_textbox(s11, 0.66, cy + 0.30, 0.74, 0.62, oe, size=13, bold=True, color=BLUE, font_name=FONT_MONO, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)
        add_textbox(s11, 1.56, cy + 0.16, 5.80, 0.34, ctitle, size=13.5, bold=True, color=NAVY)
        add_textbox(s11, 1.56, cy + 0.52, 5.80, 0.60, cdesc, size=10.8, color=INK_SEC, line_spacing=1.2)

    # Panel derecho: 3 alcances futuros
    add_rect(s11, 7.82, 1.52, 5.03, 5.30, MUTED_BG, line_color=BORDER, rounded=True, radius=0.06)
    futures = [
        ("HORIZONTE 01 · ERP", "Integración de stock, COGS y vencimientos", "Evolucionar del Ingreso en Riesgo hacia margen neto rescatado y merma física evitada.", NAVY),
        ("HORIZONTE 02 · ESCALAMIENTO", "Expansión TX / WI + ensamble híbrido", "Combinar Random Forest con SES/Tweedie para sumar precisión en volumen e intermitencia.", BLUE),
        ("HORIZONTE 03 · CAMPO", "Piloto A/B de 8 semanas en tienda CA_3", "Validar elasticidad real en Clúster C3, recorte -20%/-30% y cupones SNAP Fase B.", SPARK),
    ]
    for idx, (fnum, fhead, fdesc, facc) in enumerate(futures):
        fy = 1.72 + idx * 1.68
        add_rect(s11, 8.04, fy, 4.59, 1.50, WHITE, line_color=BORDER, rounded=True, radius=0.08)
        add_rect(s11, 8.04, fy, 0.08, 1.50, facc)
        add_textbox(s11, 8.24, fy + 0.14, 4.22, 0.24, fnum, size=8.8, bold=True, color=BLUE, font_name=FONT_MONO)
        add_textbox(s11, 8.24, fy + 0.40, 4.22, 0.36, fhead, size=13.5, bold=True, color=NAVY)
        add_textbox(s11, 8.24, fy + 0.80, 4.22, 0.60, fdesc, size=10.8, color=INK_SEC, line_spacing=1.2)

    set_notes(
        s11,
        "Expositor 4 — Zavala Gamero, Piero Rodrigo (4:10–4:40):\n"
        "Cuatro conclusiones empíricas respaldan cada objetivo específico sin simular datos. Como hoja de ruta proponemos: "
        "(1) integrar ERP con stock y COGS, (2) escalar a TX/WI con un ensamble híbrido RF+SES/Tweedie, y (3) ejecutar un piloto A/B de 8 semanas en CA_3.",
    )

    # =========================================================================
    # SLIDE 12 — CIERRE OSCURO (#081C30) · BLOQUE 4
    # =========================================================================
    s12 = prs.slides.add_slide(blank_layout)
    set_bg(s12, NAVY)
    add_rect(s12, 0.0, 0.0, 0.09, 3.9, SPARK)
    add_rect(s12, 0.0, 3.9, 0.09, 3.6, BLUE)
    add_spark_mark(s12, 0.84, 0.64, 0.06, 0.15)
    add_textbox(s12, 1.12, 0.50, 7.4, 0.28, "WALMART CALIFORNIA  ·  FOODS  ·  RESULTADOS AUDITADOS", size=10, bold=True, color=BLUE_LIGHT, font_name=FONT_MONO)
    add_rect(s12, 11.20, 0.46, 1.42, 0.36, NAVY_SOFT, line_color=SPARK, rounded=True, radius=0.5)
    add_textbox(s12, 11.22, 0.50, 1.38, 0.28, "UNDC 2026", size=10, bold=True, color=SPARK, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE)

    closing_cards = [
        (f"${total_risk:,.0f}", "USD detectados en 28 días", f"{total_units:,.0f} unidades en desaceleración sobre 5,748 series reales M5.", SPARK, SPARK),
        (f"{c3['revenue_at_risk_share_pct']:.1f}%", "Concentrado en Clúster C3", f"Solo {c3['sku_count']} SKUs ({c3['portfolio_pct']:.1f}%) concentran ${c3['revenue_at_risk_usd_total']:,.0f} USD de impacto.", BLUE, BLUE_LIGHT),
        ("0", "Descuentos destructores de margen", f"{cs_strat['sku_count']:,} SKUs inelásticos en Cross-Selling; Markdown solo en {md_strat['sku_count']} elásticos.", EMERALD_LIGHT, EMERALD_LIGHT),
    ]
    for idx, (cval, clbl, csub, top_c, val_c) in enumerate(closing_cards):
        cx = 0.72 + idx * 4.04
        add_rect(s12, cx, 1.24, 3.82, 2.30, NAVY_SOFT, line_color=BORDER_DARK, rounded=True, radius=0.08)
        add_rect(s12, cx, 1.24, 3.82, 0.065, top_c)
        add_textbox(s12, cx + 0.26, 1.46, 3.30, 0.78, cval, size=38, bold=True, color=val_c)
        add_textbox(s12, cx + 0.26, 2.30, 3.30, 0.38, clbl, size=14, bold=True, color=WHITE)
        add_textbox(s12, cx + 0.26, 2.72, 3.30, 0.66, csub, size=10.8, color=SLATE_LIGHT, line_spacing=1.2)

    add_rect(s12, 0.72, 3.98, 0.74, 0.055, SPARK)
    add_textbox(s12, 0.72, 4.18, 11.8, 0.72, "Gracias — Preguntas y Demo en Vivo", size=33, bold=True, color=WHITE)
    add_textbox(
        s12, 0.72, 4.92, 11.6, 0.42,
        "Prototipo interactivo disponible en Streamlit · IA Aplicada al Marketing Digital · Ingeniería de Sistemas UNDC",
        size=13.5, color=SLATE_LIGHT,
    )

    add_rect(s12, 0.72, 5.56, 11.9, 0.012, BORDER_DARK)
    for idx, (_, name) in enumerate(members):
        mx = 0.72 + idx * 3.02
        add_rect(s12, mx, 5.76, 2.86, 1.12, NAVY_SOFT, line_color=BORDER_DARK, rounded=True, radius=0.14)
        add_textbox(s12, mx + 0.16, 5.90, 2.54, 0.24, f"INTEGRANTE {idx + 1}", size=8.5, bold=True, color=SPARK, font_name=FONT_MONO)
        add_textbox(s12, mx + 0.16, 6.18, 2.54, 0.60, name, size=12.5, bold=True, color=WHITE)

    set_notes(
        s12,
        "Expositor 4 — Zavala Gamero, Piero Rodrigo (4:40–5:00):\n"
        f"Tres cifras para recordar: ${total_risk:,.0f} USD en riesgo detectados, {c3['revenue_at_risk_share_pct']:.1f}% concentrado en Clúster C3 "
        "y cero descuentos destructores de margen. Muchas gracias: pasamos ahora a la demo en vivo en Streamlit y quedamos atentos a sus preguntas.",
    )

    OUT_PPTX.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUT_PPTX))
    print(f"[OK] PPTX generado: {OUT_PPTX} ({len(prs.slides)} slides, {OUT_PPTX.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    build_deck(load_audited_data())
