"""
Job Tracker — Web UI (Streamlit)
"""
import os
import sys
import subprocess
from pathlib import Path
import streamlit as st

# Asegurar que el raíz del proyecto esté en el path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.database import init_db, get_jobs, get_job, update_job, get_stats, VALID_STATUSES
from src.config import load_config

# ─── Inicialización ────────────────────────────────────────────────────────────
init_db()

st.set_page_config(
    page_title="Job Tracker",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="collapsed",
)

STATUS_COLORS = {
    "new": "#00bfff",
    "reviewing": "#ffd700",
    "applied": "#32cd32",
    "interview": "#00ff7f",
    "rejected": "#ff4444",
    "offer": "#00ff00",
    "discarded": "#888888",
}

STATUS_EMOJI = {
    "new": "🆕", "reviewing": "👀", "applied": "📤",
    "interview": "🎯", "rejected": "❌", "offer": "🎉", "discarded": "🗑️",
}


def badge(status: str) -> str:
    color = STATUS_COLORS.get(status, "#ccc")
    emoji = STATUS_EMOJI.get(status, "")
    return f'<span style="background:{color};color:#000;padding:2px 8px;border-radius:12px;font-size:0.8em;font-weight:600">{emoji} {status}</span>'


# ─── Tabs ──────────────────────────────────────────────────────────────────────
tab_jobs, tab_scrape, tab_ai, tab_config = st.tabs(
    ["💼 Vacantes", "🔍 Scrape", "🤖 IA", "⚙️ Config"]
)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — VACANTES
# ═══════════════════════════════════════════════════════════════════════════════
with tab_jobs:
    st.title("Vacantes")

    # Stats resumen
    stats = get_stats()
    total = sum(stats.values())
    cols = st.columns(len(VALID_STATUSES) + 1)
    cols[0].metric("Total", total)
    for i, s in enumerate(VALID_STATUSES):
        cols[i + 1].metric(f"{STATUS_EMOJI.get(s,'')} {s}", stats.get(s, 0))

    st.divider()

    # Filtros
    col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
    with col_f1:
        filter_status = st.selectbox(
            "Filtrar por estado",
            ["todos"] + VALID_STATUSES,
            index=0,
        )
    with col_f2:
        search_text = st.text_input("Buscar en título / empresa", placeholder="ej: DevOps, AWS...")
    with col_f3:
        limit = st.number_input("Límite", min_value=10, max_value=500, value=50, step=10)

    jobs = get_jobs(status=filter_status if filter_status != "todos" else None, limit=int(limit))

    if search_text:
        q = search_text.lower()
        jobs = [j for j in jobs if q in j["title"].lower() or q in j["company"].lower()]

    if not jobs:
        st.info("No hay vacantes con los filtros seleccionados.")
    else:
        st.caption(f"{len(jobs)} vacantes")

        # Tabla
        header = st.columns([1, 4, 3, 3, 2, 3, 2])
        for col, label in zip(header, ["ID", "Título", "Empresa", "Ubicación", "Fuente", "Estado", "Fecha"]):
            col.markdown(f"**{label}**")
        st.divider()

        for job in jobs:
            row = st.columns([1, 4, 3, 3, 2, 3, 2])
            row[0].write(job["id"])
            row[1].write(job["title"])
            row[2].write(job["company"])
            loc = (job["location"] or "") + (" 🌐" if job["remote"] else "")
            row[3].write(loc)
            row[4].write(job["source"])
            row[5].markdown(badge(job["status"]), unsafe_allow_html=True)
            row[6].write((job["date_found"] or "")[:10])

    st.divider()

    # Panel de detalle / edición
    st.subheader("Detalle de vacante")
    job_id_input = st.number_input("ID de vacante", min_value=1, step=1, value=1)

    if st.button("Cargar vacante"):
        job = get_job(int(job_id_input))
        if job:
            st.session_state["selected_job"] = dict(job)
        else:
            st.error(f"Vacante #{job_id_input} no encontrada.")

    if "selected_job" in st.session_state:
        j = st.session_state["selected_job"]
        c1, c2 = st.columns(2)
        c1.markdown(f"**{j['title']}** @ {j['company']}")
        c1.markdown(f"📍 {j['location']} {'🌐' if j['remote'] else ''}")
        c1.markdown(f"💰 {j['salary'] or 'Sin salario'}")
        c1.markdown(f"🔗 [{j['url'][:60]}...]({j['url']})")

        with c2:
            new_status = st.selectbox(
                "Estado", VALID_STATUSES,
                index=VALID_STATUSES.index(j["status"]) if j["status"] in VALID_STATUSES else 0,
                key="status_select"
            )
            new_notes = st.text_area("Notas", value=j.get("notes") or "", key="notes_area")
            if st.button("Guardar cambios"):
                update_job(j["id"], status=new_status, notes=new_notes)
                st.session_state["selected_job"]["status"] = new_status
                st.session_state["selected_job"]["notes"] = new_notes
                st.success("Guardado.")

        if j.get("description"):
            with st.expander("Ver descripción completa"):
                st.text(j["description"][:3000])

        if j.get("cover_letter_path") and Path(j["cover_letter_path"]).exists():
            with open(j["cover_letter_path"], "rb") as f:
                st.download_button(
                    "⬇️ Descargar cover letter",
                    data=f,
                    file_name=Path(j["cover_letter_path"]).name,
                    mime="application/pdf",
                )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — SCRAPE
# ═══════════════════════════════════════════════════════════════════════════════
with tab_scrape:
    st.title("Scrape de vacantes")

    all_sources = [
        "remotive", "wwr", "linkedin", "computrabajo", "occ",
        "remoteok", "himalayas", "torre", "getonboard", "wellfound",
        "hireline", "honeypot", "infojobs", "jobicy",
    ]

    selected_sources = st.multiselect(
        "Fuentes a scrapeear",
        options=all_sources,
        default=["remotive", "himalayas", "remoteok", "getonboard"],
    )

    col_btn, col_note = st.columns([1, 3])
    run_btn = col_btn.button("▶ Iniciar scrape", type="primary", disabled=not selected_sources)
    col_note.caption("El scrape puede tardar varios minutos dependiendo de las fuentes seleccionadas.")

    if run_btn and selected_sources:
        sources_arg = ",".join(selected_sources)
        output_box = st.empty()
        log_lines = []

        with st.spinner("Scrapeando..."):
            proc = subprocess.Popen(
                [sys.executable, str(ROOT / "main.py"), "scrape", "--sources", sources_arg],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(ROOT),
                env={**os.environ},
            )
            for line in proc.stdout:
                log_lines.append(line.rstrip())
                output_box.code("\n".join(log_lines[-40:]), language="")
            proc.wait()

        if proc.returncode == 0:
            st.success("Scrape completado.")
        else:
            st.error(f"Scrape terminó con código {proc.returncode}.")

        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — IA
# ═══════════════════════════════════════════════════════════════════════════════
with tab_ai:
    st.title("Análisis IA")

    gemini_ok = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    groq_ok = bool(os.environ.get("GROQ_API_KEY", "").strip())
    openrouter_ok = bool(os.environ.get("OPENROUTER_API_KEY", "").strip())
    claude_ok = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())

    if not gemini_ok and not groq_ok and not openrouter_ok and not claude_ok:
        st.warning(
            "No hay API key configurada. Agrega una de estas en tu `.env`:\n\n"
            "- **GROQ_API_KEY** — gratis: https://console.groq.com/keys\n"
            "- **GEMINI_API_KEY** — gratis: https://aistudio.google.com/app/apikey\n"
            "- **ANTHROPIC_API_KEY**"
        )
    else:
        if gemini_ok:
            provider = "Gemini ✅"
        elif groq_ok:
            provider = "Groq (llama-3.3-70b) ✅"
        elif openrouter_ok:
            provider = "OpenRouter (llama-3.3-70b) ✅"
        else:
            provider = "Claude (Anthropic) ✅"
        st.success(f"Proveedor activo: **{provider}**")

    st.divider()
    ai_job_id = st.number_input("ID de vacante", min_value=1, step=1, key="ai_job_id")

    col_t, col_cv, col_cl = st.columns(3)

    if col_t.button("📊 Analizar fit (ATS)"):
        job = get_job(int(ai_job_id))
        if not job:
            st.error("Vacante no encontrada.")
        elif not job["description"]:
            st.error("Esta vacante no tiene descripción.")
        else:
            with st.spinner("Analizando con IA..."):
                try:
                    from src.cv_tailor import analyze_fit
                    result = analyze_fit(job["title"], job["company"], job["description"])
                    st.session_state["tailor_result"] = result
                    st.session_state["tailor_job"] = dict(job)
                except Exception as e:
                    st.error(f"Error: {e}")

    if "tailor_result" in st.session_state:
        r = st.session_state["tailor_result"]
        score = r.get("match_score", 0)
        color = "green" if score >= 70 else ("orange" if score >= 45 else "red")
        st.markdown(f"### ATS Score: :{color}[{score}/100]")
        st.caption(r.get("overall_verdict", ""))

        mc, mmc = st.columns(2)
        with mc:
            st.markdown("**Keywords encontradas en tu CV:**")
            st.write(" · ".join(r.get("matched_keywords", [])) or "—")
        with mmc:
            st.markdown("**Keywords que faltan:**")
            st.write(" · ".join(r.get("missing_keywords", [])) or "—")

        if r.get("critical_gaps"):
            st.markdown("**Gaps críticos:**")
            for g in r["critical_gaps"]:
                st.markdown(f"- ❌ {g}")

        if r.get("reword_suggestions"):
            st.markdown("**Sugerencias de rewording:**")
            for s in r["reword_suggestions"]:
                st.markdown(f"- `{s.get('cv_phrase','')}` → **{s.get('suggested','')}**")

    if col_cv.button("📄 Generar CV tailored"):
        job = get_job(int(ai_job_id))
        if not job:
            st.error("Vacante no encontrada.")
        elif not job["description"]:
            st.error("Esta vacante no tiene descripción.")
        else:
            with st.spinner("Generando CV personalizado..."):
                try:
                    from src.cv_tailor import analyze_fit, generate_tailored_cv
                    tailor = st.session_state.get("tailor_result") or analyze_fit(
                        job["title"], job["company"], job["description"]
                    )
                    path = generate_tailored_cv(
                        job_id=job["id"], job_title=job["title"],
                        company=job["company"], description=job["description"],
                        url=job["url"], tailor_result=tailor,
                    )
                    with open(path, "rb") as f:
                        st.download_button(
                            "⬇️ Descargar CV tailored",
                            data=f,
                            file_name=Path(path).name,
                            mime="application/pdf",
                        )
                    st.success(f"CV generado: {Path(path).name}")
                except Exception as e:
                    st.error(f"Error: {e}")

    if col_cl.button("✉️ Generar cover letter"):
        job = get_job(int(ai_job_id))
        if not job:
            st.error("Vacante no encontrada.")
        else:
            with st.spinner("Generando cover letter..."):
                try:
                    from src.cover_letter import generate_cover_letter
                    path = generate_cover_letter(
                        job_id=job["id"], job_title=job["title"],
                        company=job["company"], description=job["description"],
                        url=job["url"],
                    )
                    update_job(job["id"], cover_letter_path=path, status="reviewing")
                    with open(path, "rb") as f:
                        st.download_button(
                            "⬇️ Descargar cover letter",
                            data=f,
                            file_name=Path(path).name,
                            mime="application/pdf",
                        )
                    st.success(f"Cover letter generada: {Path(path).name}")
                except Exception as e:
                    st.error(f"Error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
with tab_config:
    st.title("Configuración")

    cfg = load_config()

    # Subir CV
    st.subheader("CV")
    data_dir = Path(os.environ.get("DATA_DIR", ROOT / "data"))
    cv_path = data_dir / "cv.pdf"
    if cv_path.exists():
        st.success(f"CV cargado: `{cv_path.name}` ({cv_path.stat().st_size // 1024} KB)")
    else:
        st.warning("No hay CV cargado aún.")

    uploaded = st.file_uploader("Subir nuevo CV (PDF)", type=["pdf"])
    if uploaded:
        data_dir.mkdir(parents=True, exist_ok=True)
        cv_path.write_bytes(uploaded.read())
        st.success(f"CV guardado en {cv_path}")

    st.divider()

    # Info de configuración activa
    st.subheader("Configuración activa")
    profile = cfg.get("profile", {})
    c1, c2 = st.columns(2)
    c1.markdown(f"**Nombre:** {profile.get('name', '—')}")
    c1.markdown(f"**Email:** {profile.get('email', '—')}")
    c2.markdown(f"**Proveedor IA activo:** {'Gemini' if os.environ.get('GEMINI_API_KEY') else 'Claude' if os.environ.get('ANTHROPIC_API_KEY') else '⚠️ Ninguno'}")
    c2.markdown(f"**Modelo Claude:** {cfg.get('anthropic', {}).get('model', 'claude-sonnet-4-6')}")

    st.divider()
    st.subheader("Keywords de búsqueda")
    keywords = cfg.get("search", {}).get("keywords", [])
    st.write(", ".join(keywords))

    st.subheader("Fuentes activas (scrape diario)")
    st.write(", ".join([
        "remotive", "wwr", "linkedin", "computrabajo", "occ",
        "remoteok", "himalayas", "getonboard", "jobicy", "glassdoor",
    ]))

    st.divider()
    st.caption("Para modificar keywords, locations o filtros edita `config.yaml` y reinicia el contenedor.")
