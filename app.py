import streamlit as st
from pathlib import Path
from bot import scrape_project, project_name_from_url

DEFAULT_SAVE_DIR = ""

st.set_page_config(page_title="Here you go babe <3", layout="centered")

st.markdown(
    """
    <style>
    .stApp { max-width: 720px; margin: 0 auto; }
    .status-box {
        background: #1e1e2e; border-radius: 8px; padding: 12px 16px;
        font-family: monospace; font-size: 13px; color: #cdd6f4;
        max-height: 300px; overflow-y: auto; margin-top: 8px;
    }
    .status-line { margin: 2px 0; }
    .success { color: #a6e3a1; }
    .fail { color: #f38ba8; }
    .info { color: #89b4fa; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Arch daily paywall skip hack crazy gamer wowziers")
st.caption("Paste da project url (only works for archdaily btw)")

site_url = st.text_input(
    "Project URL",
    placeholder="https://www.archdaily.com/12345/project-name",
)

save_dir = st.text_input(
    "Destination folder",
    value=DEFAULT_SAVE_DIR,
    help="go to whatever path you want and check waha pe",
)

if site_url:
    project_name = project_name_from_url(site_url)
    full_path = Path(save_dir) / project_name
    st.info(f"Images will be saved to: **{full_path}**")

col1, col2 = st.columns([1, 3])
start = col1.button("Download", type="primary", use_container_width=True, disabled=not site_url)

if start and site_url:
    save_path = Path(save_dir)
    if not save_path.exists():
        try:
            save_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            st.error(f"Cannot create folder: {e}")
            st.stop()

    progress_bar = st.progress(0, text="Starting ...")
    log_container = st.empty()
    log_lines: list[str] = []

    def on_progress(stage, current, total, message):
        if stage == "scan":
            progress_bar.progress(0, text="Scanning project page ...")
            log_lines.append(f'<div class="status-line info">{message}</div>')
        elif stage == "found":
            log_lines.append(f'<div class="status-line info">{message}</div>')
        elif stage == "error":
            log_lines.append(f'<div class="status-line fail">{message}</div>')
        elif stage == "download":
            pct = current / total if total else 0
            progress_bar.progress(pct, text=f"Downloading {current} / {total}")
            css = "success" if "Saved" in message else ("fail" if "failed" in message.lower() else "info")
            log_lines.append(f'<div class="status-line {css}">{message}</div>')

        log_container.markdown(
            f'<div class="status-box">{"".join(log_lines)}</div>',
            unsafe_allow_html=True,
        )

    saved, total, project_name = scrape_project(site_url, save_path, on_progress=on_progress)

    progress_bar.progress(1.0, text="Complete!")

    if saved > 0:
        st.success(f"Hurraahahhh :^ {saved}/{total} images saved to **{project_name}/**")
    elif total == 0:
        st.warning("No image pages found. Check if the URL is a valid ArchDaily project page.")
    else:
        st.error(f"No images could be downloaded ({total} pages found but all failed).")
