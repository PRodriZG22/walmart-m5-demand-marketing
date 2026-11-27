"""Captura automática en alta nitidez (@2x) de las 3 pestañas clave del dashboard Streamlit."""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import FIGURES_DIR, ensure_directories  # noqa: E402

STREAMLIT_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "streamlit.exe"
DASHBOARD_PATH = PROJECT_ROOT / "app" / "dashboard.py"
PORT = 8516
BASE_URL = f"http://127.0.0.1:{PORT}"

BROWSER_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"),
]


def find_local_browser() -> Path:
    for path in BROWSER_CANDIDATES:
        if path.exists():
            return path
    raise FileNotFoundError("No se encontró Edge, Chrome ni Brave instalado localmente.")


def wait_for_streamlit(timeout_sec: float = 40.0) -> None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE_URL}/_stcore/health", timeout=2) as resp:
                if resp.status == 200:
                    return
        except Exception:
            pass
        time.sleep(0.5)
    raise TimeoutError(f"Streamlit no respondió en {BASE_URL} tras {timeout_sec}s")


def wait_for_render_complete(page, expected_plots: int = 1) -> None:
    """Espera a que desaparezca el indicador de ejecución de Streamlit y rendericen los SVG Plotly."""
    # Esperar que el widget de estado "Running" no esté visible
    for _ in range(40):
        running = page.locator('[data-testid="stStatusWidget"]').count()
        plots = page.locator(".js-plotly-plot .main-svg").count()
        if running == 0 and plots >= expected_plots:
            break
        time.sleep(0.5)
    # Espera adicional para estabilizar animaciones/fuentes/layout de Plotly
    time.sleep(2.2)


def capture_streamlit_tab(page, output_path: Path, max_height: int = 1650) -> tuple[int, int]:
    """Ajusta la altura del viewport al contenido real del contenedor principal de Streamlit y captura PNG."""
    # Colapsar sidebar si queremos foco total? No: mantener 1440px con sidebar limpio se ve ejecutivo;
    # primero aseguramos scroll arriba y medimos altura real del contenedor principal.
    page.evaluate(
        """() => {
            const main = document.querySelector('[data-testid="stMain"]') || document.querySelector('section.main');
            if (main) main.scrollTop = 0;
            window.scrollTo(0, 0);
        }"""
    )
    time.sleep(0.5)
    content_h = page.evaluate(
        """() => {
            const inner = document.querySelector('[data-testid="stMainBlockContainer"]')
                || document.querySelector('.block-container');
            if (!inner) return 1100;
            const rect = inner.getBoundingClientRect();
            return Math.ceil(rect.top + inner.scrollHeight + 36);
        }"""
    )
    target_h = max(960, min(int(content_h), max_height))
    page.set_viewport_size({"width": 1440, "height": target_h})
    # Forzar resize de Plotly tras cambiar el alto del viewport
    page.evaluate("window.dispatchEvent(new Event('resize'));")
    time.sleep(1.5)
    page.evaluate(
        """() => {
            const main = document.querySelector('[data-testid="stMain"]') || document.querySelector('section.main');
            if (main) main.scrollTop = 0;
            window.scrollTo(0, 0);
        }"""
    )
    time.sleep(0.4)
    page.screenshot(path=str(output_path), full_page=False)
    return 1440, target_h


def main() -> None:
    ensure_directories()
    browser_exe = find_local_browser()
    print(f"Usando navegador local: {browser_exe}")

    proc = subprocess.Popen(
        [
            str(STREAMLIT_EXE),
            "run",
            str(DASHBOARD_PATH),
            "--server.headless",
            "true",
            "--server.port",
            str(PORT),
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        print(f"Iniciando Streamlit headless en {BASE_URL}...")
        wait_for_streamlit(timeout_sec=45.0)
        print("  [OK] Streamlit activo.")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=str(browser_exe),
                headless=True,
                args=["--disable-gpu", "--no-sandbox"],
            )
            context = browser.new_context(
                viewport={"width": 1440, "height": 960},
                device_scale_factor=2,
                color_scheme="light",
            )
            page = context.new_page()
            page.goto(BASE_URL, wait_until="networkidle", timeout=60000)
            wait_for_render_complete(page, expected_plots=2)

            # Colapsar sidebar vía JS click (en Streamlit 1.67 el botón aparece al hacer hover)
            collapse_btn = page.locator('[data-testid="stSidebarCollapseButton"] button')
            if collapse_btn.count() > 0:
                collapse_btn.first.evaluate("el => el.click()")
                time.sleep(0.9)
                page.evaluate("window.dispatchEvent(new Event('resize'));")
                time.sleep(1.0)

            # 1) Pestaña 1 — Resumen Ejecutivo
            out1 = FIGURES_DIR / "fig09_dashboard_tab1_resumen.png"
            w1, h1 = capture_streamlit_tab(page, out1, max_height=1450)
            print(f"  [OK] Capturada {out1.name} ({w1}x{h1} @2x, {out1.stat().st_size/1024:.1f} KB)")

            # 2) Pestaña 2 — Decisión por Producto (FOODS_3_282 · Tienda CA_3 por defecto)
            page.set_viewport_size({"width": 1440, "height": 960})
            page.get_by_role("tab", name="2. Decisión por Producto").click()
            wait_for_render_complete(page, expected_plots=1)
            # Confirmar que FOODS_3_282 · Tienda CA_3 está visible en pantalla
            body_t2 = page.inner_text("body")
            assert "FOODS_3_282" in body_t2 and "CA_3" in body_t2, "FOODS_3_282 CA_3 no está seleccionado en Tab 2"
            out2 = FIGURES_DIR / "fig10_dashboard_tab2_producto.png"
            w2, h2 = capture_streamlit_tab(page, out2, max_height=1450)
            print(f"  [OK] Capturada {out2.name} ({w2}x{h2} @2x, {out2.stat().st_size/1024:.1f} KB)")

            # 3) Pestaña 3 — Simulador de Campañas (25% / Esperado ε=0.6 por defecto)
            page.set_viewport_size({"width": 1440, "height": 960})
            page.get_by_role("tab", name="3. Simulador de Campañas").click()
            wait_for_render_complete(page, expected_plots=1)
            body_t3 = page.inner_text("body")
            assert "-20% a -30%" in body_t3 and "25%" in body_t3, "Simulador 25% no visible en Tab 3"
            out3 = FIGURES_DIR / "fig11_dashboard_tab3_simulador.png"
            w3, h3 = capture_streamlit_tab(page, out3, max_height=1620)
            print(f"  [OK] Capturada {out3.name} ({w3}x{h3} @2x, {out3.stat().st_size/1024:.1f} KB)")

            browser.close()

        print("Capturas fig09..fig11 completadas con éxito.")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("Servidor Streamlit temporal detenido.")


if __name__ == "__main__":
    main()
