import streamlit as st
import tempfile
import zipfile
import shutil
import io
from pathlib import Path
from bot import scrape_project, project_name_from_url

st.set_page_config(page_title="Here you go babe <3", layout="centered")

st.markdown(
    """
    <style>
    .stApp { max-width: 720px; margin: 0 auto; }
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

start = st.button("Download", type="primary", use_container_width=True, disabled=not site_url)

if start and site_url:
    tmp_dir = Path(tempfile.mkdtemp())

    progress_bar = st.progress(0, text="Starting ...")
    status_text = st.empty()

    def on_progress(stage, current, total, message):
        if stage == "scan":
            progress_bar.progress(0, text="Scanning project page ...")
        elif stage == "found":
            status_text.info(f"Found {total} image(s)")
        elif stage == "error":
            status_text.error(message)
        elif stage == "download":
            pct = current / total if total else 0
            progress_bar.progress(pct, text=f"Downloading {current} / {total}")

    saved, total, project_name = scrape_project(site_url, tmp_dir, on_progress=on_progress)

    progress_bar.progress(1.0, text="Complete!")

    if saved > 0:
        project_dir = tmp_dir / project_name

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for img_file in sorted(project_dir.iterdir()):
                if img_file.is_file():
                    zf.write(img_file, f"{project_name}/{img_file.name}")
        zip_buf.seek(0)

        status_text.success(f"Hurraahahhh :^ {saved}/{total} images downloaded!")

        st.download_button(
            label=f"Save ZIP ({saved} images)",
            data=zip_buf,
            file_name=f"{project_name}.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
        )
    elif total == 0:
        st.warning("No image pages found. Check if the URL is a valid ArchDaily project page.")
    else:
        st.error(f"No images could be downloaded ({total} pages found but all failed).")

    shutil.rmtree(tmp_dir, ignore_errors=True)
