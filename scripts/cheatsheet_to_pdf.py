import sys
from pathlib import Path

import matplotlib.pyplot as plt


def render_text_pdf(input_path: str, output_path: str | None = None):
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Cheat sheet not found: {input_file}")
    content = input_file.read_text(encoding="utf-8")

    # Prepare output path
    if output_path is None:
        out = input_file.with_suffix("")
        output_file = Path("outputs") / f"{out.name}.pdf"
    else:
        output_file = Path(output_path)
        if output_file.is_dir():
            output_file = output_file / f"{input_file.stem}.pdf"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Render using matplotlib on a letter-sized page
    fig = plt.figure(figsize=(8.5, 11.0), dpi=150)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")

    # Use monospaced font and wrap text by inserting newlines (matplotlib doesn't auto-wrap multi-line strings gracefully).
    ax.text(
        0.05,
        0.95,
        content,
        va="top",
        ha="left",
        family="monospace",
        fontsize=8,
        wrap=True,
    )

    fig.savefig(output_file, format="pdf")
    plt.close(fig)
    print(f"✓ PDF saved to: {output_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/cheatsheet_to_pdf.py <cheatsheet_txt_path> [output_pdf_path_or_dir]", file=sys.stderr)
        sys.exit(1)
    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    render_text_pdf(input_path, output_path)
