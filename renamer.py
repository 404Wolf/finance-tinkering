import re
from pathlib import Path

HTML_DIR = Path("output")

CONDITIONAL_RE = re.compile(
    r"Conditional result:\s*(-?[0-9]+(?:\.[0-9]+)?)"
)


def rename_html_files():
    for html_file in HTML_DIR.glob("*.html"):
        if html_file.name == "index.html":
            continue

        text = html_file.read_text(encoding="utf-8")

        matches = CONDITIONAL_RE.findall(text)
        if not matches:
            print(f"Skipping (no conditional result): {html_file.name}")
            continue

        final_value = matches[-1]

        if final_value.startswith("-"):
            numeric = final_value[1:].replace(".", "_")
            value_str = f"neg{numeric}"
        else:
            value_str = final_value.replace(".", "_")

        ticker = html_file.stem.split("-")[0]
        new_name = f"{ticker}-{value_str}.html"
        new_path = html_file.with_name(new_name)

        if new_path.exists():
            print(f"Skipping (target exists): {new_name}")
            continue

        html_file.rename(new_path)
        print(f"Renamed: {html_file.name} -> {new_name}")


def write_index():
    links = []

    for f in sorted(HTML_DIR.glob("*.html")):
        if f.name == "index.html":
            continue
        links.append(f'<li><a href="{f.name}">{f.stem}</a></li>')

    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Ticker Runs</title>
</head>
<body>
<h1>Ticker Runs</h1>
<ul>
{''.join(links)}
</ul>
</body>
</html>
"""

    (HTML_DIR / "index.html").write_text(html, encoding="utf-8")
    print("Regenerated index.html")


if __name__ == "__main__":
    rename_html_files()
    write_index()
