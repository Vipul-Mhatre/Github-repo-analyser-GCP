from flask import Flask, render_template, request, redirect
import os, subprocess, shutil, sqlite3
from pathlib import Path
from collections import Counter

app = Flask(__name__)
DB_NAME = "repo_data.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS repo_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_name TEXT,
            readme_word_count INTEGER,
            repo_size_kb REAL,
            last_commit TEXT,
            languages TEXT,
            has_license BOOLEAN,
            file_count INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def insert_repo_data(repo_name, word_count, size_kb, commit_info, lang_summary, has_license, file_count):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO repo_info 
        (repo_name, readme_word_count, repo_size_kb, last_commit, languages, has_license, file_count)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (repo_name, word_count, size_kb, commit_info, lang_summary, has_license, file_count))
    conn.commit()
    conn.close()

def clone_repo(url, dest):
    try:
        subprocess.run(["git", "clone", url, str(dest)], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False

def extract_readme(repo_path):
    readme_path = repo_path / "README.md"
    return readme_path.read_text(encoding='utf-8') if readme_path.exists() else ""

def extract_license(repo_path):
    for name in ["LICENSE", "LICENSE.txt"]:
        if (repo_path / name).exists():
            return True
    return False

def list_files(repo_path):
    return [os.path.relpath(os.path.join(root, f), repo_path) 
            for root, _, files in os.walk(repo_path) for f in files]

def count_languages(files):
    return Counter(Path(f).suffix.lower() for f in files if Path(f).suffix)

def get_last_commit_info(repo_path):
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "log", "-1", "--pretty=format:%h - %s (%cd)"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return "No commit info found."

def analyze_repo(url):
    repo_name = url.rstrip("/").split("/")[-1].replace(".git", "")
    current_dir = Path(__file__).resolve().parent
    repo_path = current_dir / repo_name

    if not clone_repo(url, repo_path):
        return

    readme = extract_readme(repo_path)
    license_found = extract_license(repo_path)
    files = list_files(repo_path)
    lang_stats = count_languages(files)
    word_count = len(readme.split())
    size_kb = sum(f.stat().st_size for f in repo_path.glob("**/*") if f.is_file()) / 1024
    commit_info = get_last_commit_info(repo_path)
    lang_summary = ", ".join(f"{ext[1:]}: {count}" for ext, count in lang_stats.items())
    
    insert_repo_data(repo_name, word_count, round(size_kb, 2), commit_info, lang_summary, license_found, len(files))
    shutil.rmtree(repo_path)

@app.route("/", methods=["GET"])
def home():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM repo_info ORDER BY id DESC")
    repos = cursor.fetchall()
    conn.close()
    return render_template("repo_analyse.html", repos=repos)

@app.route("/analyze", methods=["POST"])
def analyze():
    url = request.form["repo_url"].strip()
    analyze_repo(url)
    return redirect("/")

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
