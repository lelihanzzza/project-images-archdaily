import streamlit as st
import tempfile
import zipfile
import shutil
import io
import platform
from pathlib import Path, PureWindowsPath
from bot import scrape_project, project_name_from_url

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

_running_locally = platform.system() == "Windows" or Path.home().exists()
_is_windows = platform.system() == "Windows"

save_dir = st.text_input(
    "Local save folder (optional, works when running locally)",
    value="",
    placeholder=r"C:\Users\YourName\Downloads" if _is_windows else "~/Downloads",
    help="Leave blank to just use the download button. "
         "If you're running this locally, paste a Windows path like C:\\Users\\You\\Pictures",
)

if site_url:
    project_name = project_name_from_url(site_url)
    if save_dir.strip():
        norm_path = Path(PureWindowsPath(save_dir)) if _is_windows else Path(save_dir)
        full_path = norm_path / project_name
        st.info(f"Images will also be saved to: **{full_path}**")
    else:
        st.info("Images will be available as a ZIP download after scraping.")

col1, col2 = st.columns([1, 3])
start = col1.button("Download", type="primary", use_container_width=True, disabled=not site_url)

if start and site_url:
    tmp_dir = Path(tempfile.mkdtemp())

    local_save_path = None
    if save_dir.strip():
        try:
            norm = Path(PureWindowsPath(save_dir)) if _is_windows else Path(save_dir).expanduser()
            if not norm.exists():
                norm.mkdir(parents=True, exist_ok=True)
            local_save_path = norm
        except OSError as e:
            st.warning(f"Can't write to local folder ({e}). Images will still be available for download.")

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

    saved, total, project_name = scrape_project(site_url, tmp_dir, on_progress=on_progress)

    progress_bar.progress(1.0, text="Complete!")

    if saved > 0:
        project_dir = tmp_dir / project_name

        if local_save_path:
            local_project_dir = local_save_path / project_name
            try:
                if local_project_dir.exists():
                    shutil.rmtree(local_project_dir)
                shutil.copytree(project_dir, local_project_dir)
                st.success(f"Hurraahahhh :^ {saved}/{total} images saved to **{local_project_dir}**")
            except OSError as e:
                st.warning(f"Couldn't copy to local folder: {e}")

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for img_file in sorted(project_dir.iterdir()):
                if img_file.is_file():
                    zf.write(img_file, f"{project_name}/{img_file.name}")
        zip_buf.seek(0)

        st.download_button(
            label=f"Download ZIP ({saved} images)",
            data=zip_buf,
            file_name=f"{project_name}.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
        )

        if not local_save_path:
            st.success(f"Hurraahahhh :^ {saved}/{total} images ready for download!")
    elif total == 0:
        st.warning("No image pages found. Check if the URL is a valid ArchDaily project page.")
    else:
        st.error(f"No images could be downloaded ({total} pages found but all failed).")

    shutil.rmtree(tmp_dir, ignore_errors=True)
