from __future__ import annotations

import json
import sys
import hashlib
from pathlib import Path

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parent
LOGO_PATH = APP_DIR / "assets" / "Logo_Agora.png"
PARSER_SCRIPTS_DIR = APP_DIR / "scripts"
GPT_NORMALIZER_URL = "https://chatgpt.com/g/g-69e85b6c3d948191989f3312e8a95094-normalizador-spss-ipesquisa"

if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
if str(PARSER_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(PARSER_SCRIPTS_DIR))

from spss_builder_app_utils import (  # noqa: E402
    QuestionBlock,
    QuestionOption,
    QuestionnaireDocument,
    append_new_block,
    blocks_to_json,
    delete_block,
    document_summary,
    label_bytes,
    load_document_from_text,
    make_runtime_dir,
    serialize_document,
    write_runtime_input,
)
from spss_sanity_check import run_sanity_check  # noqa: E402


st.set_page_config(
    page_title="Ágora SPSS Builder",
    page_icon="🧩",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def inject_css() -> None:
    st.markdown(
        """
        <style>
            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(255, 102, 71, 0.10), transparent 22%),
                    radial-gradient(circle at top right, rgba(255, 191, 0, 0.12), transparent 28%),
                    linear-gradient(180deg, #fffaf5 0%, #fffdf9 38%, #ffffff 100%);
                color: #2b2b2b;
            }
            .block-container {
                padding-top: 1.2rem;
                padding-bottom: 2rem;
                max-width: 1450px;
            }
            .agora-hero {
                border: 1px solid rgba(233, 84, 32, 0.15);
                background: linear-gradient(135deg, rgba(255,255,255,0.96), rgba(255,247,239,0.98));
                border-radius: 18px;
                padding: 1.25rem 1.4rem 1.05rem 1.4rem;
                box-shadow: 0 16px 40px rgba(76, 42, 0, 0.08);
                margin-bottom: 0.45rem;
            }
            .agora-title {
                font-size: 2rem;
                line-height: 1.1;
                font-weight: 700;
                color: #6a1b12;
                margin: 0;
            }
            .agora-subtitle {
                margin: 0.4rem 0 0 0;
                color: #7a5a50;
                font-size: 0.98rem;
            }
            .agora-top-card {
                border: 1px solid rgba(233, 84, 32, 0.10);
                background: rgba(255,255,255,0.96);
                border-radius: 18px;
                padding: 1rem 1.15rem;
                box-shadow: 0 12px 30px rgba(76, 42, 0, 0.06);
                min-height: 112px;
            }
            .agora-brand-divider {
                width: 1px;
                align-self: stretch;
                background: linear-gradient(180deg, rgba(40,40,48,0.05), rgba(40,40,48,0.18), rgba(40,40,48,0.05));
                margin: 0 0.5rem;
            }
            .agora-file-card {
                border: 1px solid rgba(233, 84, 32, 0.12);
                background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(255,249,245,0.96));
                border-radius: 16px;
                padding: 0.9rem 1rem;
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.9);
            }
            .agora-status-pill {
                display: inline-flex;
                align-items: center;
                gap: 0.35rem;
                border-radius: 999px;
                padding: 0.22rem 0.6rem;
                background: rgba(227, 246, 232, 0.95);
                border: 1px solid rgba(127, 191, 141, 0.4);
                color: #36724d;
                font-size: 0.84rem;
                font-weight: 600;
                margin-top: 0;
            }
            .agora-status-pill.is-pending {
                background: rgba(255, 245, 224, 0.96);
                border: 1px solid rgba(224, 172, 73, 0.42);
                color: #9a6a12;
            }
            .agora-file-placeholder {
                font-size: 0.92rem;
                color: #7f625d;
                margin: 0 0 0.55rem 0;
            }
            .agora-separator {
                height: 1px;
                background: linear-gradient(90deg, rgba(40,40,48,0.10), rgba(40,40,48,0.45), rgba(40,40,48,0.10));
                margin: -2.05rem 0 0.35rem 0;
            }
            .agora-metric {
                border: 1px solid rgba(233, 84, 32, 0.12);
                background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(255,248,243,0.96));
                border-radius: 14px;
                padding: 0.85rem 1rem;
                min-height: 92px;
            }
            .agora-metric-label {
                font-size: 0.78rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.04em;
                color: #8f6a60;
                margin-bottom: 0.35rem;
            }
            .agora-metric-value {
                font-size: 1.45rem;
                font-weight: 700;
                color: #4e2219;
            }
            .agora-metric-note {
                font-size: 0.82rem;
                color: #896d66;
                margin-top: 0.15rem;
            }
            .agora-mini-stat {
                margin-top: 0.55rem;
                padding: 0.45rem 0.55rem;
                border: 1px solid rgba(233, 84, 32, 0.10);
                border-radius: 10px;
                background: rgba(255,255,255,0.72);
            }
            .agora-mini-stat-label {
                font-size: 0.72rem;
                color: #8f6a60;
                margin: 0 0 0.1rem 0;
            }
            .agora-mini-stat-value {
                font-size: 1.05rem;
                font-weight: 700;
                color: #4e2219;
                margin: 0;
                line-height: 1;
            }
            .stExpander {
                border: 1px solid rgba(233, 84, 32, 0.12) !important;
                border-radius: 14px !important;
                background: rgba(255,255,255,0.93) !important;
                box-shadow: 0 10px 22px rgba(76, 42, 0, 0.04);
            }
            .stExpander summary {
                font-size: 0.96rem !important;
                font-weight: 600 !important;
                color: #57261d !important;
            }
            .stExpander details[open] summary {
                color: #ffffff !important;
            }
            .stExpander details[open] summary * {
                color: #ffffff !important;
            }
            .stExpander details[open] summary svg {
                fill: #ffffff !important;
            }
            .agora-footer {
                border: 1px solid rgba(233, 84, 32, 0.16);
                background: rgba(255,255,255,0.95);
                border-radius: 18px;
                padding: 1rem 1.1rem;
                margin-top: 1rem;
                box-shadow: 0 16px 36px rgba(76, 42, 0, 0.06);
            }
            .agora-status-ok {
                color: #0f7b4d;
                font-weight: 700;
            }
            .agora-status-blocked {
                color: #b12828;
                font-weight: 700;
            }
            .agora-help {
                color: #7f625d;
                font-size: 0.9rem;
            }
            div[data-testid="stDownloadButton"] button,
            div[data-testid="stButton"] button,
            div[data-testid="stFormSubmitButton"] button,
            div[data-testid="stLinkButton"] a {
                border-radius: 12px !important;
                font-weight: 600 !important;
                color: #ffffff !important;
                background: #23242d !important;
                border: 1px solid rgba(35, 36, 45, 0.95) !important;
                transition: all 0.18s ease !important;
            }
            div[data-testid="stDownloadButton"] button:hover,
            div[data-testid="stButton"] button:hover,
            div[data-testid="stFormSubmitButton"] button:hover,
            div[data-testid="stLinkButton"] a:hover {
                background: #ffffff !important;
                color: #23242d !important;
                border: 1px solid rgba(35, 36, 45, 0.65) !important;
            }
            div[data-testid="stButton"] button[kind="primary"] {
                background: linear-gradient(180deg, #ff5b57, #ff4a47) !important;
                border: 1px solid rgba(255, 74, 71, 0.95) !important;
                color: #ffffff !important;
            }
            div[data-testid="stButton"] button[kind="primary"]:hover {
                background: #ffffff !important;
                color: #ff4a47 !important;
                border: 1px solid rgba(255, 74, 71, 0.75) !important;
            }
            div[data-testid="stDownloadButton"] button:disabled,
            div[data-testid="stButton"] button:disabled,
            div[data-testid="stFormSubmitButton"] button:disabled {
                color: rgba(255,255,255,0.48) !important;
                background: #23242d !important;
                border: 1px solid rgba(35, 36, 45, 0.75) !important;
            }
            div[data-testid="stDownloadButton"] button:disabled:hover,
            div[data-testid="stButton"] button:disabled:hover,
            div[data-testid="stFormSubmitButton"] button:disabled:hover {
                color: rgba(255,255,255,0.48) !important;
                background: #23242d !important;
                border: 1px solid rgba(35, 36, 45, 0.75) !important;
            }
            div[data-testid="stLinkButton"] a {
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                text-decoration: none !important;
                min-height: 2.45rem !important;
                padding: 0.28rem 0.48rem !important;
                font-size: 0.76rem !important;
                width: 100% !important;
            }
            [data-testid="stFileUploaderDropzone"] {
                background: rgba(255,255,255,0.86) !important;
                border: 1px dashed rgba(233, 84, 32, 0.26) !important;
                border-radius: 14px !important;
                padding: 0.35rem 0.45rem !important;
                min-height: 4.25rem !important;
            }
            [data-testid="stFileUploaderDropzone"] > div {
                min-height: 3.4rem !important;
                display: flex !important;
                align-items: center !important;
            }
            [data-testid="stFileUploaderDropzone"] section {
                margin: 0 !important;
                width: 100% !important;
            }
            [data-testid="stFileUploaderDropzone"] * {
                color: #7a5a50 !important;
            }
            .agora-upload-hint {
                color: #7f625d;
                font-size: 0.92rem;
            }
            .agora-workflow-title {
                font-size: 1.05rem;
                font-weight: 700;
                color: #4e2219;
                margin: 0 0 0.75rem 0;
            }
            .agora-workflow-card {
                border: 1px solid rgba(233, 84, 32, 0.14);
                background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(255,249,245,0.95));
                border-radius: 16px;
                padding: 1rem 1rem 0.85rem 1rem;
                min-height: 132px;
                box-shadow: 0 10px 24px rgba(76, 42, 0, 0.05);
                margin-bottom: 0.55rem;
            }
            .agora-workflow-card.is-active {
                border-color: rgba(255, 74, 71, 0.28);
                background: linear-gradient(180deg, rgba(255, 245, 244, 0.98), rgba(255, 239, 236, 0.96));
            }
            .agora-workflow-top {
                display: flex;
                align-items: center;
                gap: 0.75rem;
                margin-bottom: 0.7rem;
            }
            .agora-workflow-step {
                width: 2rem;
                height: 2rem;
                border-radius: 999px;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                background: #ffffff;
                border: 1px solid rgba(35, 36, 45, 0.18);
                color: #23242d;
                font-weight: 700;
                font-size: 1rem;
                flex: 0 0 auto;
            }
            .agora-workflow-card.is-active .agora-workflow-step {
                border-color: rgba(255, 74, 71, 0.55);
                color: #ff4a47;
            }
            .agora-workflow-heading {
                font-size: 1rem;
                font-weight: 700;
                color: #3e241e;
                margin: 0;
                line-height: 1.25;
            }
            .agora-workflow-note {
                font-size: 0.88rem;
                color: #846761;
                margin: 0;
                line-height: 1.4;
                min-height: 3.25em;
            }
            div[data-testid="column"]:has(.agora-workflow-shell) {
                border: 1px solid rgba(233, 84, 32, 0.14);
                background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(255,249,245,0.95));
                border-radius: 16px;
                padding: 1rem 1rem 0.9rem 1rem;
                min-height: 210px;
                box-shadow: 0 10px 24px rgba(76, 42, 0, 0.05);
            }
            div[data-testid="column"]:has(.agora-workflow-shell) > div[data-testid="stVerticalBlock"] {
                height: 100%;
                display: flex;
                flex-direction: column;
            }
            div[data-testid="column"]:has(.agora-workflow-shell.is-active) {
                border-color: rgba(255, 74, 71, 0.24);
                background: linear-gradient(180deg, rgba(255, 246, 245, 0.98), rgba(255, 240, 238, 0.96));
            }
            div[data-testid="column"]:has(.agora-workflow-shell) .agora-workflow-shell {
                display: flex;
                flex-direction: column;
                margin-bottom: 0.95rem;
            }
            div[data-testid="column"]:has(.agora-workflow-shell) .element-container:has(.agora-workflow-shell) {
                flex: 1 1 auto;
            }
            div[data-testid="column"]:has(.agora-workflow-shell) .element-container:has(div[data-testid="stButton"]),
            div[data-testid="column"]:has(.agora-workflow-shell) .element-container:has(div[data-testid="stDownloadButton"]) {
                margin-top: auto;
            }
            div[data-testid="column"]:has(.agora-workflow-shell) div[data-testid="stButton"] button,
            div[data-testid="column"]:has(.agora-workflow-shell) div[data-testid="stDownloadButton"] button {
                background: transparent !important;
                color: #23242d !important;
                border: 1px solid rgba(35, 36, 45, 0.14) !important;
                box-shadow: none !important;
            }
            div[data-testid="column"]:has(.agora-workflow-shell) div[data-testid="stButton"] button:hover,
            div[data-testid="column"]:has(.agora-workflow-shell) div[data-testid="stDownloadButton"] button:hover {
                background: rgba(255,255,255,0.9) !important;
                color: #1f2028 !important;
                border: 1px solid rgba(35, 36, 45, 0.28) !important;
            }
            div[data-testid="column"]:has(.agora-workflow-shell.is-active) div[data-testid="stButton"] button {
                color: #ff4a47 !important;
                border: 1px solid rgba(255, 74, 71, 0.24) !important;
            }
            div[data-testid="column"]:has(.agora-workflow-shell.is-active) div[data-testid="stButton"] button:hover {
                background: rgba(255,255,255,0.9) !important;
                color: #d83f3c !important;
                border: 1px solid rgba(255, 74, 71, 0.4) !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def init_state() -> None:
    defaults = {
        "document": QuestionnaireDocument(
            questionario="Novo Questionário",
            versao="1",
            obs="Arquivo aberto no Ágora SPSS Builder.",
            blocks=[],
        ),
        "source_name": "nenhum arquivo carregado",
        "dirty": False,
        "current_txt": "",
        "validation_result": None,
        "schema_text": "",
        "schema_path": "",
        "sav_bytes": None,
        "sav_name": "",
        "txt_name": "",
        "loaded_once": False,
        "uploaded_signature": "",
        "show_replace_uploader": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_validation() -> None:
    st.session_state.validation_result = None
    st.session_state.schema_text = ""
    st.session_state.schema_path = ""
    st.session_state.sav_bytes = None
    st.session_state.sav_name = ""


def load_text_into_state(text: str, source_name: str) -> None:
    st.session_state.document = load_document_from_text(text)
    st.session_state.source_name = source_name
    st.session_state.current_txt = serialize_document(st.session_state.document)
    st.session_state.txt_name = f"{Path(source_name).stem or 'questionario'}.txt"
    st.session_state.dirty = False
    st.session_state.loaded_once = True
    st.session_state.show_replace_uploader = False
    clear_validation()


def load_pasted_text_into_state(text: str) -> None:
    clean_text = text.strip()
    if not clean_text:
        return
    load_text_into_state(clean_text, "TXT colado.txt")
    st.session_state.uploaded_signature = hashlib.md5(clean_text.encode("utf-8")).hexdigest()


def top_header() -> None:
    left, middle, right = st.columns([2.08, 0.17, 1.04], vertical_alignment="center")
    with left:
        brand_logo, brand_divider, brand_text = st.columns([1.05, 0.06, 2.15], vertical_alignment="center")
        with brand_logo:
            st.markdown("<div style='height:0.22rem'></div>", unsafe_allow_html=True)
            if LOGO_PATH.exists():
                st.image(str(LOGO_PATH), use_container_width=True)
        with brand_divider:
            st.markdown('<div class="agora-brand-divider"></div>', unsafe_allow_html=True)
        with brand_text:
            st.markdown("<div style='height:0.22rem'></div>", unsafe_allow_html=True)
            st.markdown(
                """
                <p class="agora-title">Ágora SPSS Builder</p>
                <p class="agora-subtitle">
                    Editor técnico de questionário Ipesquisa.
                </p>
                """,
                unsafe_allow_html=True,
            )

    with middle:
        st.markdown("<div style='height:1.78rem'></div>", unsafe_allow_html=True)
        st.link_button(
            "GPT",
            GPT_NORMALIZER_URL,
            use_container_width=True,
            help="Abrir GPT Normalizer no navegador.",
        )

    with right:
        if st.session_state.loaded_once:
            status_class = "agora-status-pill is-pending" if st.session_state.dirty else "agora-status-pill"
            status_text = "Altera&ccedil;&otilde;es pendentes" if st.session_state.dirty else "Sincronizado"
            status_icon = "!" if st.session_state.dirty else "&#10003;"
            st.markdown("<div style='height:0.55rem'></div>", unsafe_allow_html=True)
            row1_left, row1_right = st.columns([1.0, 1.0], gap="small", vertical_alignment="center")
            with row1_left:
                st.markdown(
                    f'<div class="{status_class}">{status_icon} {status_text}</div>',
                    unsafe_allow_html=True,
                )
            with row1_right:
                st.markdown("<div style='margin-top:0.28rem'></div>", unsafe_allow_html=True)
                if st.button("Trocar TXT", use_container_width=True, key="toggle_replace_uploader_top"):
                    st.session_state.show_replace_uploader = not st.session_state.show_replace_uploader

            if st.session_state.show_replace_uploader:
                uploaded = st.file_uploader(
                    "Selecione um novo TXT",
                    type=["txt"],
                    key="replace_uploader_top",
                    label_visibility="collapsed",
                    help="Envie outro questionário técnico para substituir o atual.",
                )
                if uploaded is not None:
                    try:
                        file_bytes = uploaded.getvalue()
                        signature = hashlib.md5(file_bytes).hexdigest()
                        if st.session_state.uploaded_signature != signature:
                            text = file_bytes.decode("utf-8-sig")
                            load_text_into_state(text, uploaded.name)
                            st.session_state.uploaded_signature = signature
                            st.rerun()
                    except Exception as exc:
                        st.error(f"Não foi possível ler o arquivo enviado: {type(exc).__name__}: {exc}")
        else:
            st.markdown("<div style='margin-top:2.60rem'></div>", unsafe_allow_html=True)
            uploaded = st.file_uploader(
                "Carregar TXT técnico",
                type=["txt"],
                key="initial_uploader_top",
                label_visibility="collapsed",
                help="Envie o questionário técnico gerado pelo GPT Normalizer.",
            )
            if uploaded is not None:
                try:
                    file_bytes = uploaded.getvalue()
                    signature = hashlib.md5(file_bytes).hexdigest()
                    if st.session_state.uploaded_signature != signature:
                        text = file_bytes.decode("utf-8-sig")
                        load_text_into_state(text, uploaded.name)
                        st.session_state.uploaded_signature = signature
                        st.rerun()
                except Exception as exc:
                    st.error(f"Não foi possível ler o arquivo enviado: {type(exc).__name__}: {exc}")

    st.markdown('<div class="agora-separator"></div>', unsafe_allow_html=True)


def render_upload_band() -> None:
    left, right = st.columns([1.8, 1.1], vertical_alignment="bottom")
    with left:
        st.markdown('<div class="agora-separator"></div>', unsafe_allow_html=True)
        if st.session_state.loaded_once:
            toolbar_left, toolbar_right = st.columns([1.4, 1], vertical_alignment="center")
            with toolbar_left:
                st.markdown(
                    '<div class="agora-upload-hint">Arquivo carregado. Use o botão ao lado para trocar o TXT quando quiser.</div>',
                    unsafe_allow_html=True,
                )
            with toolbar_right:
                if st.button("Trocar TXT técnico", use_container_width=True, key="toggle_replace_uploader"):
                    st.session_state.show_replace_uploader = not st.session_state.show_replace_uploader

            if st.session_state.show_replace_uploader:
                st.markdown("<div style='margin-top:0.35rem'></div>", unsafe_allow_html=True)
                uploaded = st.file_uploader(
                    "Selecione um novo TXT",
                    type=["txt"],
                    key="replace_uploader",
                    help="Envie outro questionário técnico para substituir o atual.",
                )
                if uploaded is not None:
                    try:
                        file_bytes = uploaded.getvalue()
                        signature = hashlib.md5(file_bytes).hexdigest()
                        if st.session_state.uploaded_signature != signature:
                            text = file_bytes.decode("utf-8-sig")
                            load_text_into_state(text, uploaded.name)
                            st.session_state.uploaded_signature = signature
                            st.rerun()
                    except Exception as exc:
                        st.error(f"Não foi possível ler o arquivo enviado: {type(exc).__name__}: {exc}")
        else:
            uploaded = st.file_uploader(
                "Carregar TXT técnico",
                type=["txt"],
                help="Envie o questionário técnico gerado pelo GPT Normalizer.",
            )
            if uploaded is not None:
                try:
                    file_bytes = uploaded.getvalue()
                    signature = hashlib.md5(file_bytes).hexdigest()
                    if st.session_state.uploaded_signature != signature:
                        text = file_bytes.decode("utf-8-sig")
                        load_text_into_state(text, uploaded.name)
                        st.session_state.uploaded_signature = signature
                        st.rerun()
                except Exception as exc:
                    st.error(f"Não foi possível ler o arquivo enviado: {type(exc).__name__}: {exc}")
    with right:
        st.markdown(
            f"""
            <div class="agora-help">
                <strong>Fonte atual:</strong><br>
                {st.session_state.source_name}<br><br>
                <strong>Status local:</strong><br>
                {"alterações pendentes" if st.session_state.dirty else "sincronizado com o editor"}
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_document_metadata() -> None:
    st.subheader("Identidade do questionário")
    col1, col2 = st.columns([2, 1])
    with col1:
        questionario = st.text_input("Título técnico", value=st.session_state.document.questionario, key="doc_questionario")
        obs = st.text_area("Observação", value=st.session_state.document.obs, height=100, key="doc_obs")
    with col2:
        versao = st.text_input("Versão", value=st.session_state.document.versao, key="doc_versao")
        if st.button("Aplicar metadados", use_container_width=True):
            st.session_state.document.questionario = questionario
            st.session_state.document.versao = versao
            st.session_state.document.obs = obs
            st.session_state.current_txt = serialize_document(st.session_state.document)
            st.session_state.dirty = False
            clear_validation()
            st.success("Metadados aplicados ao documento base.")


def render_summary_metrics() -> None:
    summary = document_summary(st.session_state.document)
    cols = st.columns(5)
    metrics = [
        ("Perguntas", summary["total_blocos"], "total de blocos"),
        ("RU", summary["total_ru"], "resposta única"),
        ("RM", summary["total_rm"], "múltiplas respostas"),
        ("Abertas", summary["total_aberta_texto"] + summary["total_aberta_numero"], "texto + número"),
        ("Maior label", summary["max_label_bytes"], "bytes Windows-1252"),
    ]
    for col, (label, value, note) in zip(cols, metrics):
        with col:
            st.markdown(
                f"""
                <div class="agora-metric">
                    <div class="agora-metric-label">{label}</div>
                    <div class="agora-metric-value">{value}</div>
                    <div class="agora-metric-note">{note}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_actions() -> None:
    st.markdown('<p class="agora-workflow-title">Fluxo de trabalho</p>', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4, gap="medium")

    with col1:
        st.markdown(
            """
            <div class="agora-workflow-shell is-active">
                <div class="agora-workflow-top">
                    <div class="agora-workflow-step">1</div>
                    <p class="agora-workflow-heading">Aplicar alterações</p>
                </div>
                <p class="agora-workflow-note">Sincronize o documento base com as correções.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Aplicar alterações", use_container_width=True):
            st.session_state.current_txt = serialize_document(st.session_state.document)
            st.session_state.txt_name = f"{st.session_state.document.questionario or 'questionario'}.txt"
            st.session_state.dirty = False
            clear_validation()
            st.success("Alterações consolidadas no documento base.")

    with col2:
        st.markdown(
            """
            <div class="agora-workflow-shell">
                <div class="agora-workflow-top">
                    <div class="agora-workflow-step">2</div>
                    <p class="agora-workflow-heading">Validar estrutura</p>
                </div>
                <p class="agora-workflow-note">Verifique a integridade técnica do questionário.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Validar", use_container_width=True):
            run_validation()

    with col3:
        st.markdown(
            """
            <div class="agora-workflow-shell">
                <div class="agora-workflow-top">
                    <div class="agora-workflow-step">3</div>
                    <p class="agora-workflow-heading">Baixar TXT</p>
                </div>
                <p class="agora-workflow-note">Faça o download do TXT técnico atualizado.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        txt_data = st.session_state.current_txt or serialize_document(st.session_state.document)
        txt_name = (st.session_state.txt_name or "questionario.txt").replace("/", "-")
        st.download_button(
            "Baixar TXT",
            data=txt_data.encode("utf-8"),
            file_name=txt_name,
            mime="text/plain",
            use_container_width=True,
        )

    with col4:
        st.markdown(
            """
            <div class="agora-workflow-shell">
                <div class="agora-workflow-top">
                    <div class="agora-workflow-step">4</div>
                    <p class="agora-workflow-heading">Gerar .sav</p>
                </div>
                <p class="agora-workflow-note">Baixe o arquivo final com segurança após a validação.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        download_disabled = not (
            st.session_state.validation_result
            and st.session_state.validation_result.get("status") == "apto"
            and st.session_state.sav_bytes
        )
        st.download_button(
            "Download .sav",
            data=st.session_state.sav_bytes or b"",
            file_name=st.session_state.sav_name or "questionario.sav",
            mime="application/octet-stream",
            use_container_width=True,
            disabled=download_disabled,
        )


def normalize_options_df(df: pd.DataFrame) -> list[QuestionOption]:
    options: list[QuestionOption] = []
    if df is None:
        return options
    used_numeric_codes: set[int] = set()

    def clean_cell(value: object) -> str:
        if pd.isna(value):
            return ""
        text = str(value).strip()
        return "" if text.lower() == "nan" else text

    for _, row in df.iterrows():
        raw_code = clean_cell(row.get("code", ""))
        raw_label = clean_cell(row.get("label", ""))
        if not raw_code and not raw_label:
            continue
        if raw_code.isdigit():
            used_numeric_codes.add(int(raw_code))

    next_code = 1
    for _, row in df.iterrows():
        code = clean_cell(row.get("code", ""))
        label = clean_cell(row.get("label", ""))
        if not code and not label:
            continue
        if not code:
            while next_code in used_numeric_codes:
                next_code += 1
            code = str(next_code)
            used_numeric_codes.add(next_code)
            next_code += 1
        options.append(QuestionOption(code=code, label=label))
    return options


def render_editor() -> None:
    st.markdown('<p class="agora-workflow-title">Editor visual do questionário</p>', unsafe_allow_html=True)
    st.caption("Clique para expandir uma pergunta, editar o bloco e salvar localmente no documento base.")

    toolbar_left, _ = st.columns([1.3, 4], vertical_alignment="center")
    with toolbar_left:
        if st.button("Adicionar questão", use_container_width=True):
            block = append_new_block(st.session_state.document)
            st.session_state.current_txt = serialize_document(st.session_state.document)
            st.session_state.dirty = True
            clear_validation()
            st.success(f"Questão criada com {block.var}.")
            st.rerun()

    type_options = ["ru", "rm", "aberta_texto", "aberta_numero"]

    for idx, block in enumerate(st.session_state.document.blocks):
        badge = f"{block.tipo.upper()} · {block.var}"
        preview = block.label if len(block.label) <= 110 else block.label[:107].rstrip() + "..."
        title = f"{preview}    [{badge}]"
        with st.expander(title, expanded=False):
            with st.form(f"block_form_{idx}"):
                col_label, col_info = st.columns([2.3, 1], vertical_alignment="top")
                with col_label:
                    new_label = st.text_area(
                        "Pergunta",
                        value=block.label,
                        height=92,
                        key=f"label_{idx}",
                    )
                with col_info:
                    st.text_input("VAR", value=block.var, disabled=True, key=f"var_{idx}")
                    new_tipo = st.selectbox(
                        "Tipo de pergunta",
                        type_options,
                        index=type_options.index(block.tipo) if block.tipo in type_options else 0,
                        key=f"tipo_{idx}",
                    )

                new_tamanho = block.tamanho
                new_max = block.max_respostas
                option_rows = [{"code": opt.code, "label": opt.label} for opt in block.options]
                option_df = pd.DataFrame(option_rows, columns=["code", "label"])

                if new_tipo in {"ru", "rm"}:
                    with col_label:
                        edited_df = st.data_editor(
                            option_df,
                            key=f"options_{idx}",
                            use_container_width=True,
                            num_rows="dynamic",
                            column_config={
                                "code": st.column_config.TextColumn("Código"),
                                "label": st.column_config.TextColumn("Opção"),
                            },
                        )
                    with col_info:
                        if new_tipo == "rm":
                            new_max = str(
                                st.number_input(
                                    "Nr. máx. marcações",
                                    min_value=1,
                                    step=1,
                                    value=int(block.max_respostas or 1),
                                    key=f"max_{idx}",
                                )
                            )
                        else:
                            st.info("Resposta única não usa seleção máxima.")
                    new_options = normalize_options_df(edited_df)
                else:
                    size_col, aux_col = st.columns([1, 1])
                    with size_col:
                        if new_tipo == "aberta_texto":
                            new_tamanho = str(
                                st.number_input(
                                    "Número de caracteres",
                                    min_value=1,
                                    step=1,
                                    value=int(block.tamanho or 255),
                                    key=f"size_{idx}",
                                )
                            )
                        else:
                            st.info("Número aberto usa formato técnico do parser.")
                    with aux_col:
                        st.number_input(
                            "Casas decimais (futura versão)",
                            min_value=0,
                            step=1,
                            value=2,
                            disabled=True,
                            key=f"decimals_{idx}",
                        )
                    new_options = []
                    new_max = ""

                with st.expander("Metadados de apoio", expanded=False):
                    new_logica = st.text_area("Lógica (texto livre)", value=block.logica, height=80, key=f"logica_{idx}")
                    new_nota = st.text_area("Nota (texto livre)", value=block.nota, height=80, key=f"nota_{idx}")

                action_left, action_right = st.columns([4, 1.3], vertical_alignment="center")
                with action_left:
                    save = st.form_submit_button("Salvar bloco", use_container_width=True)
                with action_right:
                    delete = st.form_submit_button("Excluir questão", use_container_width=True)

                if delete:
                    removed = delete_block(st.session_state.document, idx)
                    st.session_state.current_txt = serialize_document(st.session_state.document)
                    st.session_state.dirty = True
                    clear_validation()
                    if removed:
                        st.success(f"Questão {removed.var} excluída do documento base.")
                    st.rerun()

                if save:
                    block.label = new_label.strip()
                    block.tipo = new_tipo
                    block.tamanho = new_tamanho.strip() if new_tipo == "aberta_texto" else ""
                    block.max_respostas = new_max.strip() if new_tipo == "rm" else ""
                    block.options = new_options if new_tipo in {"ru", "rm"} else []
                    block.logica = new_logica.strip()
                    block.nota = new_nota.strip()
                    st.session_state.document.blocks[idx] = block
                    st.session_state.current_txt = serialize_document(st.session_state.document)
                    st.session_state.dirty = True
                    clear_validation()
                    st.success(f"Bloco {block.var} salvo no documento base.")


def render_technical_tabs() -> None:
    with st.expander("Painel técnico", expanded=False):
        tab_txt, tab_json, tab_schema = st.tabs(["TXT técnico", "Estrutura JSON", "Schema / build"])

        with tab_txt:
            txt_payload = st.session_state.current_txt or serialize_document(st.session_state.document)
            st.code(txt_payload, language="text")

        with tab_json:
            st.code(blocks_to_json(st.session_state.document), language="json")

        with tab_schema:
            if st.session_state.schema_text:
                st.code(st.session_state.schema_text, language="json")
            else:
                st.info("Schema ainda não gerado nesta sessão. Use o botão Validar para produzir schema e `.sav`.")


def render_validation_panel() -> None:
    st.markdown('<div class="agora-footer">', unsafe_allow_html=True)
    st.subheader("Sanidade estrutural")
    result = st.session_state.validation_result
    if not result:
        st.markdown(
            '<p class="agora-help">Nenhuma validação executada ainda. O painel vai mostrar aqui o resultado técnico do questionário atual.</p>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return

    status = result.get("status")
    if status == "apto":
        st.markdown('<p class="agora-status-ok">Status: apto tecnicamente para gerar e baixar o .sav.</p>', unsafe_allow_html=True)
        if result.get("fallback_mode"):
            st.info(
                f"Geração online concluída com fallback de RM: `{result['fallback_mode']}`. "
                "O modo MRSETS falhou neste ambiente hospedado para este questionário."
            )
        art = result.get("artifacts", {})
        st.write(f"Schema: `{art.get('schema_path', '')}`")
        st.write(f"SAV: `{art.get('sav_path', '')}`")
    else:
        st.markdown('<p class="agora-status-blocked">Status: bloqueado por erro estrutural.</p>', unsafe_allow_html=True)

    st.write(f"Erros encontrados: **{result.get('error_count', 0)}**")
    for error in result.get("errors", []):
        location = error.get("var") or f"linha {error.get('line')}" if error.get("line") else "bloco"
        st.error(f"[{error.get('code')}] {error.get('message')} ({location})")

    st.markdown("</div>", unsafe_allow_html=True)


def _should_retry_with_slots(result: dict) -> bool:
    for error in result.get("errors", []):
        if error.get("code") != "sav_build_failed":
            continue
        message = error.get("message", "")
        if "UnicodeDecodeError" in message:
            return True
    return False


def run_validation() -> None:
    run_dir = make_runtime_dir()
    base_name = st.session_state.document.questionario or "questionario"
    txt_path, output_base = write_runtime_input(st.session_state.document, run_dir, base_name)
    result = run_sanity_check(txt_path, output_base, "mrsets")
    if result.get("status") != "apto" and _should_retry_with_slots(result):
        slots_output_base = output_base.with_name(output_base.name + "_slots")
        slots_result = run_sanity_check(txt_path, slots_output_base, "slots")
        if slots_result.get("status") == "apto":
            slots_result["fallback_mode"] = "slots"
            slots_result["fallback_reason"] = "mrsets_unicode_decode_error"
            result = slots_result
    st.session_state.validation_result = result
    st.session_state.current_txt = txt_path.read_text(encoding="utf-8")

    schema_path = result.get("artifacts", {}).get("schema_path")
    if schema_path and Path(schema_path).exists():
        st.session_state.schema_text = Path(schema_path).read_text(encoding="utf-8")
        st.session_state.schema_path = schema_path
    else:
        st.session_state.schema_text = ""
        st.session_state.schema_path = ""

    sav_path = result.get("artifacts", {}).get("sav_path")
    if result.get("status") == "apto" and sav_path and Path(sav_path).exists():
        st.session_state.sav_bytes = Path(sav_path).read_bytes()
        st.session_state.sav_name = Path(sav_path).name
    else:
        st.session_state.sav_bytes = None
        st.session_state.sav_name = ""


def render_app() -> None:
    inject_css()
    init_state()
    top_header()

    if not st.session_state.loaded_once:
        paste_left, _ = st.columns([1.35, 1], vertical_alignment="top")
        with paste_left:
            with st.expander("Colar TXT técnico", expanded=False):
                pasted_txt = st.text_area(
                    "Cole aqui o TXT técnico gerado pelo GPT",
                    key="pasted_txt_top",
                    height=210,
                    label_visibility="collapsed",
                    placeholder="#QUESTIONARIO: Nome do questionario\n#VERSAO: 1\n#OBS: Normalizado para spss-questionnaire-builder-v2.\n\n#LABEL: 1. Texto da pergunta.#\n#VAR: VAR00001\n#TIPO: ru\n#OPCOES:\n1 | Sim\n2 | Nao\n#FIM",
                )
                if st.button("Carregar TXT colado", use_container_width=True, key="load_pasted_txt_top"):
                    if pasted_txt.strip():
                        try:
                            load_pasted_text_into_state(pasted_txt)
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Não foi possível carregar o TXT colado: {type(exc).__name__}: {exc}")
                    else:
                        st.warning("Cole um TXT técnico antes de carregar.")
        return

    render_summary_metrics()
    st.markdown("---")
    render_actions()
    st.markdown("<div style='margin-top:-0.8rem'></div>", unsafe_allow_html=True)

    with st.expander("Metadados do documento", expanded=False):
        render_document_metadata()

    render_editor()

    st.markdown("---")
    render_technical_tabs()
    render_validation_panel()


if __name__ == "__main__":
    render_app()
