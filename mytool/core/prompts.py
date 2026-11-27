"""Prompt texts and prompt builders, one per task. Pure string work."""

from __future__ import annotations

from mytool.core.llm import LLMRequest
from mytool.core.models import ProfileEntry

FIX_SYSTEM = """\
You are a careful code reviewer helping fix static analysis findings.

You receive one code unit (or a window of lines) with line-number prefixes of the form \
"  12 | code", plus the findings reported for it. Answer with the requested JSON only.

Rules:
- Write every explanation in Turkish, short and concrete: what is wrong and why the fix helps.
- Propose minimal, behavior-preserving fixes. Do not refactor, rename or reformat unrelated code.
- Only address the given findings. Never invent findings that were not listed.
- Each fix lists the ids of the findings it resolves in finding_ids (copy the ids exactly).
- `original` must be an exact, verbatim, contiguous substring of the given code, WITHOUT the \
line-number prefixes, keeping the original indentation and newlines. Include enough lines to \
make it unique within the code.
- `replacement` is the text that replaces `original`.
- If you are unsure, or no safe fix exists, give an explanation only: set both `original` and \
`replacement` to "".
- To delete code, set `replacement` to "".
- Syntax errors (rule `invalid-syntax` or `syntax-error`) arrive together with the whole \
file: return ONE fix that resolves all of them at once (list every syntax finding id), so the \
file parses afterwards. Its `original` spans from the first to the last line you change. Use \
4 spaces for indentation in `replacement`. Fix only what keeps the code from parsing.
"""

EXPLAIN_SYSTEM = """\
You explain source code to a developer who has not read it. Answer with the requested JSON only.

Rules:
- Write everything in Turkish, short and concrete.
- Describe what the code does and why, not how Python works.
- `purpose` is one or two sentences. `notes` lists surprising behavior, side effects, \
assumptions or pitfalls; leave it empty when there is nothing worth noting.
- Never invent functions or behavior that is not in the given code.
"""

OPTIMIZE_SYSTEM = """\
You are a performance engineer. You receive one hot code unit with line-number prefixes of the \
form "  12 | code" and real cProfile numbers measured on a workload. Answer with the requested \
JSON only.

Rules:
- Optimize for speed, guided by the profile numbers. Fix the actual bottleneck, not style.
- Keep the exact behavior, return values, side effects and printed output.
- Keep the code readable. No micro-optimizations that obscure the intent.
- Write every explanation in Turkish: what was slow and why the change is faster.
- Use category "perf" and an empty finding_ids list.
- `original` must be an exact, verbatim, contiguous substring of the given code, WITHOUT the \
line-number prefixes, keeping indentation and newlines. `replacement` replaces it.
- If you see no safe speedup, return an empty fixes list.
"""


def build_fix_prompt(req: LLMRequest) -> str:
    unit = req.unit_name or "(modül düzeyi)"
    findings = "\n".join(
        f"- id={f.id} kural={f.rule} satır={f.line}: {f.message}" for f in req.findings
    )
    return (
        f"Dosya: {req.file_name}\nDil: {req.language}\nBirim: {unit}\n"
        f"İlk satır numarası: {req.start_line}\n\nBulgular:\n{findings}\n\n"
        f"Kod:\n{req.code}\n"
    )


def build_explain_prompt(file_name: str, language: str, code: str) -> str:
    return (
        f"Dosya: {file_name}\nDil: {language}\n\n"
        "Tüm dosyayı açıkla: `summary` dosyanın genel amacı, `units` her üst düzey "
        f"fonksiyon veya sınıf için bir kayıt.\n\nKod:\n{code}\n"
    )


def build_unit_prompt(file_name: str, language: str, unit_name: str, code: str) -> str:
    return (
        f"Dosya: {file_name}\nDil: {language}\nBirim: {unit_name}\n\n"
        f"Yalnız bu birimi açıkla (`name` birim adı olsun).\n\nKod:\n{code}\n"
    )


def build_summary_prompt(file_name: str, purposes: list[tuple[str, str]]) -> str:
    lines = "\n".join(f"- {name}: {purpose}" for name, purpose in purposes)
    return (
        f"Dosya: {file_name}\n\nAşağıda dosyadaki birimlerin amaçları var. Dosyanın genel "
        "amacını 2-3 cümleyle `summary` alanına yaz; `units` boş kalsın.\n\n"
        f"Birimler:\n{lines}\n"
    )


def _entry_line(entry: ProfileEntry) -> str:
    return (
        f"- {entry.function} (satır {entry.line}): çağrı={entry.calls} "
        f"tottime={entry.tottime:.4f}s cumtime={entry.cumtime:.4f}s"
    )


def build_optimize_prompt(
    file_name: str,
    language: str,
    unit_name: str,
    start_line: int,
    code: str,
    entries: list[ProfileEntry],
    total_s: float,
) -> str:
    profile = "\n".join(_entry_line(e) for e in entries)
    return (
        f"Dosya: {file_name}\nDil: {language}\nBirim: {unit_name}\n"
        f"İlk satır numarası: {start_line}\n"
        f"Toplam profil süresi: {total_s:.4f}s\n\nProfil:\n{profile}\n\nKod:\n{code}\n"
    )


SHRINK_SYSTEM = """\
You shorten Python code without changing what it does. You receive one function or method with \
line-number prefixes of the form "  12 | code". Answer with the requested JSON only.

Rules:
- Same behavior, return values, side effects and exceptions. Fewer lines.
- Keep it readable: no clever one-liners, no comprehension nested deeper than one level.
- Keep all names, the signature (the `def` line) and the docstring unchanged.
- Every line at most 100 characters.
- Write the explanation in Turkish: what was simplified.
- Return at most one fix, category "shrink", with an empty finding_ids list.
- `original` must be an exact, verbatim, contiguous substring of the given code, WITHOUT the \
line-number prefixes, keeping indentation and newlines. `replacement` replaces it and must be \
shorter than `original`.
- If you see no safe way to shorten it, return an empty fixes list.
"""

TRANSLATE_SYSTEM = """\
You translate one segment of a Python file into another programming language. Answer with the \
requested JSON only.

Rules:
- Same behavior and idiomatic target-language code. Keep function and variable names unless the \
target language forbids them.
- Translate only the given segment. Do not repeat imports or definitions of earlier segments; \
call earlier functions by the names and signatures listed in the prompt.
- `code` is plain source text, no markdown fences, no commentary.
- `notes` lists, in Turkish, any behavior that cannot be translated exactly or needs a library \
or manual attention; leave it empty otherwise.
"""


def build_shrink_prompt(
    file_name: str, language: str, unit_name: str, start_line: int, code: str
) -> str:
    return (
        f"Dosya: {file_name}\nDil: {language}\nBirim: {unit_name}\n"
        f"İlk satır numarası: {start_line}\n\nKod:\n{code}\n"
    )


def build_translate_prompt(
    file_name: str, target: str, label: str, code: str, previous: list[str]
) -> str:
    done = "\n".join(f"- {signature}" for signature in previous) or "(yok)"
    return (
        f"Dosya: {file_name}\nHedef dil: {target}\nBölüm: {label}\n\n"
        f"Daha önce çevrilen birimler (Python imzaları):\n{done}\n\nKod:\n{code}\n"
    )
