"""
Research Assistant MVP - Streamlit app.
Upload PDFs, extract methodologies (RAG), identify research gaps, generate comparison tables.
"""

import traceback
import uuid
from pathlib import Path

import streamlit as st

from config.settings import GEMINI_API_KEY, UPLOADS_DIR, ensure_dirs
from services.embedding_service import EmbeddingService
from services.gap_analyzer import GapAnalyzer
from services.llm_service import LLMService
from services.pdf_processor import PDFProcessor
from utils.export import export_to_excel


# --- Page config ---
st.set_page_config(
    page_title="Research Assistant MVP",
    layout="wide",
)

# --- Session state initialization ---
if "uploaded_papers" not in st.session_state:
    st.session_state.uploaded_papers = []
if "paper_metadata" not in st.session_state:
    st.session_state.paper_metadata = {}
if "extracted_methodologies" not in st.session_state:
    st.session_state.extracted_methodologies = {}
if "faiss_index" not in st.session_state:
    st.session_state.faiss_index = None
if "gaps_analysis" not in st.session_state:
    st.session_state.gaps_analysis = None
if "comparison_table" not in st.session_state:
    st.session_state.comparison_table = None
if "export_report_path" not in st.session_state:
    st.session_state.export_report_path = None
if "extraction_error" not in st.session_state:
    st.session_state.extraction_error = None  # (message, traceback_str) or None
if "section_summaries" not in st.session_state:
    st.session_state.section_summaries = {}  # paper_id -> {section_name: summary}


@st.cache_resource
def get_pdf_processor() -> PDFProcessor:
    """Cached PDF processor instance."""
    return PDFProcessor()


@st.cache_resource
def get_embedding_service() -> EmbeddingService:
    """Cached embedding service (sentence-transformers + FAISS)."""
    return EmbeddingService()


@st.cache_resource
def get_llm_service() -> LLMService:
    """Cached LLM service (Gemini 2.0 Flash)."""
    return LLMService()


@st.cache_resource
def get_gap_analyzer() -> GapAnalyzer:
    """Cached gap analyzer."""
    return GapAnalyzer()


def _ensure_dirs() -> None:
    ensure_dirs()


def _methodologies_list() -> list[dict]:
    """Build list of methodology dicts with paper_id for export/LLM."""
    out = []
    for paper_id, meth in st.session_state.extracted_methodologies.items():
        m = dict(meth)
        m["paper_id"] = paper_id
        out.append(m)
    return out


# --- Sidebar: Upload ---
with st.sidebar:
    st.title("📁 Upload Papers")
    _ensure_dirs()

    uploaded_files = st.file_uploader(
        "Upload PDF files",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        for f in uploaded_files:
            if not f:
                continue
            # Avoid duplicate by name
            name = f.name
            existing_ids = [p.get("paper_id") for p in st.session_state.uploaded_papers]
            paper_id = None
            for p in st.session_state.uploaded_papers:
                if p.get("name") == name:
                    paper_id = p.get("paper_id")
                    break
            if paper_id is None:
                paper_id = f"paper_{Path(name).stem}_{uuid.uuid4().hex[:8]}"
                save_path = UPLOADS_DIR / f"{paper_id}.pdf"
                save_path.write_bytes(f.getvalue())
                try:
                    pdf_processor = get_pdf_processor()
                    result = pdf_processor.process_pdf(save_path, paper_id)
                except Exception as e:
                    st.error(f"Failed to process {name}: {e}")
                    continue
                sections = result.get("sections") or {}
                get_embedding_service().add_paper(sections, paper_id)
                st.session_state.uploaded_papers.append({
                    "paper_id": paper_id,
                    "name": name,
                    "path": str(save_path),
                })
                st.session_state.paper_metadata[paper_id] = result
                st.session_state.faiss_index = True
                st.success(f"✅ Added: {name}")
            else:
                st.info(f"Already added: {name}")

    st.subheader("Uploaded papers")
    for p in st.session_state.uploaded_papers:
        name = p.get("name", p.get("paper_id", "?"))
        st.caption(f"• {name}")

    if st.button("Clear All"):
        st.session_state.uploaded_papers = []
        st.session_state.paper_metadata = {}
        st.session_state.extracted_methodologies = {}
        st.session_state.gaps_analysis = None
        st.session_state.comparison_table = None
        st.session_state.faiss_index = None
        st.session_state.export_report_path = None
        st.session_state.section_summaries = {}
        st.rerun()


# --- Main area: Tabs ---
tab1, tab2, tab3 = st.tabs(["📊 Methodologies", "🔍 Research Gaps", "📋 Comparison"])

# --- Tab 1: Methodologies ---
with tab1:
    st.header("📊 Methodologies")
    papers = st.session_state.uploaded_papers
    st.caption(f"Uploaded papers: {len(papers)}")

    # Show last extraction error at top so it's always visible (not inside an expander)
    err = st.session_state.get("extraction_error")
    if err:
        st.error(f"**Extraction failed:** {err[0]}")
        st.caption("Details:")
        st.code(err[1])
        if st.button("Dismiss error", key="dismiss_extraction_error"):
            st.session_state.extraction_error = None
            st.rerun()

    if not papers:
        st.info("Upload PDFs in the sidebar to extract methodologies.")
    else:
        if not (GEMINI_API_KEY and GEMINI_API_KEY.strip()):
            st.warning(
                "**GEMINI_API_KEY** is not set in `.env`. Set it to use methodology extraction, gap analysis, and comparison tables."
            )
        embedding_svc = get_embedding_service()
        llm_svc = get_llm_service()

        def extract_one(paper_id: str, display_name: str) -> bool:
            """Run extraction for one paper. Returns True on success, False on error (and sets session_state.extraction_error)."""
            st.session_state.extraction_error = None
            try:
                # Get the full methodology section text from paper metadata
                paper_meta = st.session_state.paper_metadata.get(paper_id, {})
                sections = paper_meta.get("sections", {})
                
                # Try to get methodology or method section
                context = sections.get("methodology") or sections.get("method", "")
                
                # If no direct section, fall back to RAG search
                if not context.strip():
                    chunks = embedding_svc.search(
                        "methodology method dataset model experiments",
                        k=8,
                        section_filter="methodology",
                    )
                    if not chunks:
                        chunks = embedding_svc.search(
                            "methodology method dataset model experiments",
                            k=8,
                            section_filter="method",
                        )
                    if not chunks:
                        chunks = embedding_svc.search(
                            "methodology method dataset model experiments",
                            k=8,
                            section_filter=None,
                        )
                    paper_chunks = [c for c in chunks if c.get("paper_id") == paper_id]
                    if not paper_chunks:
                        paper_chunks = chunks[:5]
                    context = "\n\n".join(c.get("text", "") for c in paper_chunks)
                
                if not context.strip():
                    st.session_state.extraction_error = (
                        f"No methodology text found for {display_name}. The PDF may lack clear 'Methodology' or 'Method' sections.",
                        "",
                    )
                    return False
                with st.spinner("Extracting methodology..."):
                    meth = llm_svc.extract_methodology(context)
                st.session_state.extracted_methodologies[paper_id] = meth
                st.success(f"Extracted: {display_name}")
                return True
            except Exception as e:
                st.session_state.extraction_error = (str(e), traceback.format_exc())
                return False

        for p in papers:
            paper_id = p.get("paper_id", "")
            display_name = p.get("name", paper_id)
            with st.expander(f"📄 {display_name}"):
                if st.button("Extract Methodology", key=f"extract_{paper_id}"):
                    extract_one(paper_id, display_name)
                    st.rerun()  # Rerun so success message or extraction_error at top is visible
                meth = st.session_state.extracted_methodologies.get(paper_id)
                if meth:
                    c1, c2, c3, c4 = st.columns(4)
                    with c1:
                        st.markdown("**📊 Dataset**")
                        datasets = meth.get("datasets") or []
                        if datasets:
                            for d in datasets[:3]:
                                # Handle both string and dict formats
                                if isinstance(d, dict):
                                    st.caption(str(d.get("name") or d))
                                else:
                                    st.caption(str(d))
                        else:
                            st.caption("—")
                    with c2:
                        st.markdown("**🤖 Model**")
                        model = meth.get("model") or {}
                        if isinstance(model, dict):
                            st.caption(str(model.get("name") or "—"))
                        else:
                            st.caption(str(model) if model else "—")
                    with c3:
                        st.markdown("**📈 Metrics**")
                        metrics = meth.get("metrics") or []
                        st.caption(", ".join(str(m) for m in metrics[:5]) or "—")
                    with c4:
                        st.markdown("**📝 Summary**")
                        summary = meth.get("summary") or meth.get("contribution") or ""
                        st.caption(summary or "—")

        if st.button("Extract All Sections", key="extract_all_btn"):
            """Extract summaries for all sections in all papers."""
            for p in papers:
                paper_id = p.get("paper_id", "")
                display_name = p.get("name", paper_id)
                try:
                    with st.spinner(f"Extracting sections from {display_name}..."):
                        paper_meta = st.session_state.paper_metadata.get(paper_id, {})
                        sections = paper_meta.get("sections", {})
                        if not sections:
                            st.warning(f"No sections found in {display_name}")
                            continue
                        summaries = llm_svc.summarize_sections(sections)
                        st.session_state.section_summaries[paper_id] = summaries
                        st.success(f"Extracted {len(summaries)} sections from {display_name}")
                except Exception as e:
                    st.error(f"Failed to extract sections from {display_name}: {e}")
            st.rerun()  # Rerun to show summaries

        # Display section summaries if available
        if st.session_state.section_summaries:
            st.subheader("📚 Section Summaries")
            for paper_id, summaries in st.session_state.section_summaries.items():
                paper_name = next((p.get("name", paper_id) for p in papers if p.get("paper_id") == paper_id), paper_id)
                with st.expander(f"📄 {paper_name}", expanded=True):
                    for section_name, summary in summaries.items():
                        st.markdown(f"**{section_name.title()}**")
                        st.write(summary)
                        st.divider()


# --- Tab 2: Research Gaps ---
with tab2:
    st.header("🔍 Research Gaps")
    methodologies = _methodologies_list()

    if len(methodologies) < 2:
        st.warning("Upload and extract methodologies for at least 2 papers to analyze gaps.")
    else:
        if st.button("Analyze Gaps"):
            try:
                gap_analyzer = get_gap_analyzer()
                llm_svc = get_llm_service()
                with st.spinner("Analyzing combinations..."):
                    combinations = gap_analyzer.analyze_combinations(methodologies)
                with st.spinner("Identifying gaps with LLM..."):
                    gaps = llm_svc.identify_gaps(methodologies)
                st.session_state.gaps_analysis = {
                    "combinations": combinations,
                    "gaps": gaps,
                }
                st.success("Gap analysis complete.")
            except Exception as e:
                st.error(f"Gap analysis failed: {e}")

        ga = st.session_state.gaps_analysis
        if ga:
            gaps = ga.get("gaps") or {}
            with st.expander("Methodological Gaps", expanded=True):
                for item in (gaps.get("methodological_gaps") or []):
                    if isinstance(item, dict):
                        st.markdown(f"**{item.get('description') or item.get('value')}**")
                        st.caption(item.get("explanation") or "")
                    else:
                        st.caption(str(item))
            with st.expander("Dataset Limitations"):
                for item in (gaps.get("dataset_limitations") or []):
                    st.caption(str(item) if not isinstance(item, dict) else item.get("description") or item.get("value") or str(item))
            with st.expander("Evaluation Gaps"):
                for item in (gaps.get("evaluation_gaps") or []):
                    st.caption(str(item) if not isinstance(item, dict) else item.get("description") or item.get("value") or str(item))
            with st.expander("Novel Directions"):
                for item in (gaps.get("novel_directions") or []):
                    st.caption(str(item) if not isinstance(item, dict) else item.get("description") or item.get("value") or str(item))

            if st.button("Export Report", key="btn_export_report"):
                try:
                    out_path = Path("data") / "research_gaps_report.xlsx"
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    export_to_excel(methodologies, gaps, out_path)
                    st.session_state.export_report_path = str(out_path)
                    st.success("Report generated. Download below.")
                except Exception as e:
                    st.error(f"Export failed: {e}")
            if st.session_state.get("export_report_path"):
                p = Path(st.session_state.export_report_path)
                if p.exists():
                    with open(p, "rb") as f:
                        st.download_button(
                            "Download Excel",
                            data=f.read(),
                            file_name=p.name,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_gaps_report",
                        )


# --- Tab 3: Comparison ---
with tab3:
    st.header("📋 Comparison")
    methodologies = _methodologies_list()

    if not methodologies:
        st.info("Extract methodologies in the first tab to generate a comparison table.")
    else:
        if st.button("Generate Comparison Table"):
            try:
                llm_svc = get_llm_service()
                with st.spinner("Generating table..."):
                    table_md = llm_svc.generate_comparison_table(methodologies)
                st.session_state.comparison_table = table_md
                st.success("Table generated.")
            except Exception as e:
                st.error(f"Table generation failed: {e}")

        if st.session_state.comparison_table:
            st.markdown(st.session_state.comparison_table)
            if st.button("Export to Excel"):
                try:
                    out_path = Path("data") / "comparison_table.xlsx"
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    export_to_excel(
                        methodologies,
                        st.session_state.gaps_analysis.get("gaps") if st.session_state.gaps_analysis else None,
                        out_path,
                    )
                    with open(out_path, "rb") as f:
                        st.download_button(
                            "Download Excel",
                            data=f.read(),
                            file_name=out_path.name,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_excel_comp",
                        )
                except Exception as e:
                    st.error(f"Export failed: {e}")
            st.subheader("Copy Table")
            st.code(st.session_state.comparison_table, language="markdown")
