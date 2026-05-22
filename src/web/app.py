"""
Job Tracker — Web UI (Streamlit)
"""
import os
import sys
import subprocess
from pathlib import Path
import yaml
import streamlit as st

# Asegurar que el raíz del proyecto esté en el path
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from src.database import init_db, get_jobs, get_job, update_job, get_stats, VALID_STATUSES
from src.config import load_config
from src.web.wizard import is_first_run, run_wizard

# ─── Inicialización ────────────────────────────────────────────────────────────
init_db()

# ─── Wizard de primer uso ──────────────────────────────────────────────────────
if is_first_run() and "wizard_done" not in st.session_state:
    run_wizard()
    st.stop()

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
    st.title("⚙️ Configuración")

    # ── Subir CV ──────────────────────────────────────────────────────────────
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

    # ── Editar config.yaml ────────────────────────────────────────────────────
    st.subheader("📋 Editar configuración")

    _cfg_path = Path(os.environ.get("CONFIG_PATH", "/data/config.yaml"))

    try:
        if _cfg_path.exists():
            with open(_cfg_path, "r", encoding="utf-8") as _fh:
                _cfg_raw = yaml.safe_load(_fh) or {}
        else:
            _cfg_raw = {}
    except Exception as _load_err:
        st.error(f"No se pudo cargar config.yaml: {_load_err}")
        _cfg_raw = {}

    _s = _cfg_raw.get("search", {})
    _p = _cfg_raw.get("profile", {})
    _e = _cfg_raw.get("email", {})
    _cl = _cfg_raw.get("cover_letter", {})

    _stab_search, _stab_profile, _stab_email, _stab_cl = st.tabs(
        ["🔍 Búsqueda", "👤 Perfil", "📧 Email", "✉️ Carta de presentación"]
    )

    with _stab_search:
        _kw = st.text_area(
            "Keywords de búsqueda (una por línea)",
            value="\n".join(_s.get("keywords", [])),
            height=120, key="cfg_keywords",
        )
        _loc = st.text_area(
            "Ubicaciones (una por línea)",
            value="\n".join(_s.get("locations", [])),
            height=80, key="cfg_locations",
        )
        _remote = st.toggle(
            "Preferir empleos remotos",
            value=bool(_s.get("remote_preference", False)),
            key="cfg_remote",
        )
        _excl_kw = st.text_area(
            "Keywords excluidas (una por línea)",
            value="\n".join(_s.get("exclude_keywords", [])),
            height=80, key="cfg_excl_kw",
        )

    with _stab_profile:
        _pname = st.text_input("Nombre completo", value=_p.get("name", ""), key="cfg_p_name")
        _pemail = st.text_input("Email", value=_p.get("email", ""), key="cfg_p_email")
        _pphone = st.text_input("Teléfono", value=_p.get("phone", ""), key="cfg_p_phone")

    with _stab_email:
        _smtp_srv = st.text_input(
            "Servidor SMTP", value=_e.get("smtp_server", "smtp.gmail.com"), key="cfg_smtp_srv"
        )
        _smtp_port = st.number_input(
            "Puerto SMTP", value=int(_e.get("smtp_port", 587)),
            min_value=1, max_value=65535, key="cfg_smtp_port",
        )
        _sender = st.text_input("Remitente", value=_e.get("sender", ""), key="cfg_sender")
        _app_pass = st.text_input(
            "App Password", value=_e.get("app_password", ""),
            type="password", key="cfg_app_pass",
        )

    with _stab_cl:
        _lang_opts = ["auto", "es", "en"]
        _lang = st.selectbox(
            "Idioma", options=_lang_opts,
            index=_lang_opts.index(_cl.get("language", "auto"))
            if _cl.get("language", "auto") in _lang_opts else 0,
            key="cfg_cl_lang",
        )
        _tone_opts = ["professional", "casual", "formal"]
        _tone = st.selectbox(
            "Tono", options=_tone_opts,
            index=_tone_opts.index(_cl.get("tone", "professional"))
            if _cl.get("tone", "professional") in _tone_opts else 0,
            key="cfg_cl_tone",
        )
        _maxlen = st.number_input(
            "Longitud máxima (palabras)",
            value=int(_cl.get("max_length", 400)),
            min_value=100, max_value=1000, step=50, key="cfg_cl_maxlen",
        )

    if st.button("💾 Guardar configuración", type="primary", key="btn_save_cfg"):
        try:
            _out = dict(_cfg_raw)
            _out["search"] = {
                "keywords": [k.strip() for k in _kw.split("\n") if k.strip()],
                "locations": [l.strip() for l in _loc.split("\n") if l.strip()],
                "remote_preference": _remote,
                "exclude_keywords": [k.strip() for k in _excl_kw.split("\n") if k.strip()],
                "exclude_titles": _s.get("exclude_titles", []),
                "exclude_locations": _s.get("exclude_locations", []),
            }
            _out["profile"] = {
                "name": _pname, "email": _pemail, "phone": _pphone,
                "cv_path": _p.get("cv_path", "data/cv.pdf"),
            }
            _out["email"] = {
                "smtp_server": _smtp_srv, "smtp_port": int(_smtp_port),
                "sender": _sender, "app_password": _app_pass,
            }
            _out["cover_letter"] = {
                "language": _lang, "tone": _tone, "max_length": int(_maxlen),
            }
            _cfg_path.parent.mkdir(parents=True, exist_ok=True)
            with open(_cfg_path, "w", encoding="utf-8") as _fh:
                yaml.dump(_out, _fh, allow_unicode=True, default_flow_style=False, sort_keys=False)
            st.success("✅ Configuración guardada.")
        except Exception as _save_err:
            st.error(f"❌ Error al guardar: {_save_err}")

    st.divider()

    # ── Control del contenedor ────────────────────────────────────────────────
    st.subheader("🐳 Control del contenedor")

    try:
        import docker as _docker_sdk
        _dclient = _docker_sdk.from_env()
        _dclient.ping()
        _docker_ok = True
    except Exception:
        _docker_ok = False

    if not _docker_ok:
        st.warning(
            "⚠️ No se puede conectar al socket de Docker. "
            "Asegúrate de que el socket esté montado en el contenedor."
        )
    else:
        _project = os.environ.get("COMPOSE_PROJECT_NAME", "job-tracker")
        _dcol1, _dcol2, _dcol3 = st.columns(3)

        if _dcol1.button("🔄 Reiniciar scheduler", key="btn_restart_sched"):
            try:
                _dclient.containers.get("job-tracker-scheduler").restart()
                st.success("Scheduler reiniciado.")
            except Exception as _de:
                st.error(f"Error: {_de}")

        if _dcol2.button("🔄 Reiniciar todos", key="btn_restart_all"):
            try:
                _dctrs = _dclient.containers.list(
                    filters={"label": f"com.docker.compose.project={_project}"}
                )
                for _dc in _dctrs:
                    if _dc.name == "job-tracker-web":
                        continue
                    _dc.restart()
                st.success("Contenedores reiniciados (excepto web).")
            except Exception as _de:
                st.error(f"Error: {_de}")

        if _dcol3.button("⏹ Detener todo", key="btn_stop_all"):
            try:
                _dctrs = _dclient.containers.list(
                    filters={"label": f"com.docker.compose.project={_project}"}
                )
                for _dc in _dctrs:
                    _dc.stop()
                st.success("Contenedores detenidos.")
            except Exception as _de:
                st.error(f"Error: {_de}")
