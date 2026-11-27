"""Realistic fake findings/suggestions for the mock adapter.

The patches are self-contained Python snippets so the diff view looks real.
One suggestion has ``failed`` verification on purpose: the server must never
let it reach the UI.
"""

from __future__ import annotations

from server.contracts import (
    FileSummary,
    Finding,
    Patch,
    Suggestion,
    VerificationResult,
)

FILES: list[tuple[str, int]] = [
    ("src/billing/invoice.py", 182),
    ("src/billing/tax.py", 64),
    ("src/api/handlers.py", 241),
    ("src/utils/cache.py", 97),
    ("src/utils/text.py", 58),
    ("tests/test_invoice.py", 120),
]


def _f(
    fid: str, file: str, line: int, sev: str, rule: str, msg: str, end: int | None = None
) -> Finding:
    return Finding.model_validate(
        {
            "id": fid,
            "tool": "ruff",
            "file": file,
            "line_start": line,
            "line_end": end or line,
            "severity": sev,
            "rule_code": rule,
            "message": msg,
        }
    )


FINDINGS: list[Finding] = [
    _f(
        "F1",
        "src/billing/invoice.py",
        42,
        "warning",
        "B006",
        "Do not use mutable data structures for argument defaults",
        48,
    ),
    _f(
        "F2",
        "src/billing/invoice.py",
        97,
        "warning",
        "E711",
        "Comparison to `None` should be `cond is None`",
    ),
    _f("F3", "src/api/handlers.py", 118, "error", "E722", "Do not use bare `except`", 123),
    _f(
        "F4",
        "src/api/handlers.py",
        164,
        "warning",
        "B904",
        "Within an `except` clause, raise exceptions with `raise ... from err`",
        170,
    ),
    _f(
        "F5",
        "src/utils/cache.py",
        31,
        "warning",
        "PERF401",
        "Use a list comprehension to create a transformed list",
        35,
    ),
    _f(
        "F6",
        "src/utils/cache.py",
        58,
        "warning",
        "PERF203",
        "`try`-`except` within a loop incurs performance overhead",
        66,
    ),
    _f(
        "F7",
        "src/utils/text.py",
        22,
        "info",
        "SIM108",
        "Use ternary operator instead of `if`-`else`-block",
        25,
    ),
    _f(
        "F8",
        "src/billing/tax.py",
        19,
        "error",
        "F841",
        "Local variable `rate` is assigned to but never used",
    ),
    _f(
        "F9",
        "src/utils/text.py",
        3,
        "info",
        "UP035",
        "Import from `collections.abc` instead: `Iterable`",
    ),
    _f(
        "F10",
        "src/api/handlers.py",
        201,
        "info",
        "C401",
        "Unnecessary generator (rewrite as a set comprehension)",
    ),
    _f(
        "F11",
        "tests/test_invoice.py",
        4,
        "warning",
        "F401",
        "`decimal.ROUND_UP` imported but unused",
    ),
]


def _s(
    sid: str,
    finding_ids: list[str],
    category: str,
    title: str,
    explanation: str,
    file: str,
    original: str,
    new: str,
    status: str,
    detail: str,
    ms: int,
) -> Suggestion:
    return Suggestion.model_validate(
        {
            "id": sid,
            "finding_ids": finding_ids,
            "category": category,
            "title": title,
            "explanation": explanation,
            "patch": Patch(file=file, original_text=original, new_text=new),
            "verification": VerificationResult.model_validate(
                {"status": status, "detail": detail, "duration_ms": ms}
            ),
        }
    )


SUGGESTIONS: list[Suggestion] = [
    _s(
        "S1",
        ["F1"],
        "bug",
        "Değiştirilebilir varsayılan argüman faturalar arasında sızıyor",
        "`lines=[]` varsayılan değeri fonksiyon tanımlandığında bir kez oluşturulur ve "
        "tüm çağrılar arasında paylaşılır. İkinci faturada önceki faturanın kalemleri de "
        "görünür. Varsayılanı `None` yapıp fonksiyon içinde yeni liste oluşturmak bu "
        "sızıntıyı engeller.",
        "src/billing/invoice.py",
        "def build_invoice(customer: Customer, lines: list[Line] = []) -> Invoice:\n"
        '    """Create an invoice for *customer*."""\n'
        "    for line in customer.pending_lines():\n"
        "        lines.append(line)\n"
        "    total = sum(line.amount for line in lines)\n"
        "    return Invoice(customer=customer, lines=lines, total=total)\n",
        "def build_invoice(\n"
        "    customer: Customer, lines: list[Line] | None = None\n"
        ") -> Invoice:\n"
        '    """Create an invoice for *customer*."""\n'
        "    lines = [] if lines is None else list(lines)\n"
        "    for line in customer.pending_lines():\n"
        "        lines.append(line)\n"
        "    total = sum(line.amount for line in lines)\n"
        "    return Invoice(customer=customer, lines=lines, total=total)\n",
        "passed",
        "pytest: 14 test geçti (tests/test_invoice.py)",
        2140,
    ),
    _s(
        "S2",
        ["F2"],
        "style",
        "None karşılaştırması `is None` ile yapılmalı",
        "`== None` karşılaştırması `__eq__` metodunu çağırır ve özel sınıflarda yanlış "
        "sonuç verebilir. Kimlik karşılaştırması (`is None`) hem doğru hem de "
        "Python'da önerilen yazımdır.",
        "src/billing/invoice.py",
        "    if invoice.paid_at == None:\n        return InvoiceStatus.OPEN\n",
        "    if invoice.paid_at is None:\n        return InvoiceStatus.OPEN\n",
        "passed",
        "pytest: 14 test geçti (tests/test_invoice.py)",
        1980,
    ),
    _s(
        "S3",
        ["F3"],
        "bug",
        "Çıplak `except` tüm hataları sessizce yutuyor",
        "Çıplak `except:` `KeyboardInterrupt` ve `SystemExit` dahil her şeyi yakalar; "
        "sunucu kapatılamaz hale gelebilir ve gerçek hatalar sessizce yutulur. Yalnızca "
        "beklenen istisnayı yakalayıp günlüğe yazmak daha güvenli.",
        "src/api/handlers.py",
        "    try:\n"
        "        payload = json.loads(request.body)\n"
        "    except:\n"
        '        return error_response(400, "invalid body")\n',
        "    try:\n"
        "        payload = json.loads(request.body)\n"
        "    except json.JSONDecodeError as err:\n"
        '        logger.info("invalid JSON body: %s", err)\n'
        '        return error_response(400, "invalid body")\n',
        "passed",
        "Sözdizimi kontrolü ve pytest: 31 test geçti",
        3420,
    ),
    _s(
        "S4",
        ["F4"],
        "bug",
        "İstisna zinciri kayboluyor: `from err` eksik",
        "`except` içinde yeni bir istisna fırlatılırken `from err` kullanılmazsa asıl "
        "neden traceback'te 'During handling...' olarak karışık görünür. `from err` "
        "zinciri açıkça kurar ve hata ayıklamayı kolaylaştırır.",
        "src/api/handlers.py",
        "    try:\n"
        "        user = repo.get_user(user_id)\n"
        "    except RecordNotFound:\n"
        '        raise NotFound(f"user {user_id} not found")\n',
        "    try:\n"
        "        user = repo.get_user(user_id)\n"
        "    except RecordNotFound as err:\n"
        '        raise NotFound(f"user {user_id} not found") from err\n',
        "skipped",
        "Bu fonksiyonu kapsayan test bulunamadı; yalnızca sözdizimi kontrol edildi.",
        180,
    ),
    _s(
        "S5",
        ["F5"],
        "perf",
        "Döngü yerine liste kavrayışı kullan",
        "Döngü içinde `append` her adımda metot araması yapar. Liste kavrayışı aynı işi "
        "tek ifadede ve belirgin şekilde daha hızlı yapar.",
        "src/utils/cache.py",
        "    keys = []\n"
        "    for entry in self._entries.values():\n"
        "        if not entry.expired(now):\n"
        "            keys.append(entry.key)\n"
        "    return keys\n",
        "    return [\n"
        "        entry.key for entry in self._entries.values() if not entry.expired(now)\n"
        "    ]\n",
        "passed",
        "pytest: 9 test geçti (tests/test_cache.py)",
        1260,
    ),
    _s(
        "S6",
        ["F6"],
        "perf",
        "`try` bloğunu döngünün dışına al",
        "`try` bloğunu döngünün dışına almak istisna kurulum maliyetini azaltır.",
        "src/utils/cache.py",
        "    for key in keys:\n"
        "        try:\n"
        "            del self._entries[key]\n"
        "        except KeyError:\n"
        "            pass\n",
        "    try:\n"
        "        for key in keys:\n"
        "            del self._entries[key]\n"
        "    except KeyError:\n"
        "        pass\n",
        "failed",
        "pytest: test_evict_partial başarısız (davranış değişti)",
        1630,
    ),
    _s(
        "S7",
        ["F7"],
        "style",
        "if/else bloğu yerine koşullu ifade",
        "Dört satırlık `if`/`else` bloğu tek bir koşullu ifadeyle aynı anlamı daha "
        "okunur şekilde ifade eder.",
        "src/utils/text.py",
        '    if width > 0:\n        suffix = "…"\n    else:\n        suffix = ""\n',
        '    suffix = "…" if width > 0 else ""\n',
        "passed",
        "pytest: 6 test geçti (tests/test_text.py)",
        940,
    ),
    _s(
        "S8",
        ["F8"],
        "bug",
        "Hesaplanan KDV oranı kullanılmıyor",
        "`rate` hesaplanıyor ama hiç kullanılmıyor; aşağıdaki satır sabit `0.18` "
        "değerini kullanıyor. Büyük ihtimalle amaçlanan, hesaplanan oranın "
        "kullanılmasıydı. Bu bir mantık hatasıdır, yalnızca stil sorunu değil.",
        "src/billing/tax.py",
        "def vat_for(amount: Decimal, country: str) -> Decimal:\n"
        "    rate = VAT_RATES.get(country, DEFAULT_VAT)\n"
        '    return (amount * Decimal("0.18")).quantize(CENT)\n',
        "def vat_for(amount: Decimal, country: str) -> Decimal:\n"
        "    rate = VAT_RATES.get(country, DEFAULT_VAT)\n"
        "    return (amount * rate).quantize(CENT)\n",
        "passed",
        "pytest: 22 test geçti (tests/test_tax.py)",
        1710,
    ),
    _s(
        "S9",
        ["F10"],
        "style",
        "Gereksiz üreteç yerine küme kavrayışı",
        "`set(...)` içine verilen üreteç ifadesi yerine doğrudan küme kavrayışı "
        "kullanmak daha kısa ve biraz daha hızlıdır.",
        "src/api/handlers.py",
        "    roles = set(r.name.lower() for r in user.roles)\n",
        "    roles = {r.name.lower() for r in user.roles}\n",
        "skipped",
        "Projede test komutu bulunamadı; yalnızca sözdizimi kontrol edildi.",
        95,
    ),
    _s(
        "S10",
        ["F11"],
        "style",
        "Kullanılmayan içe aktarma",
        "`ROUND_UP` içe aktarılmış ama testlerde kullanılmıyor. Kullanılmayan içe "
        "aktarmalar okuyucuyu yanıltır ve lint gürültüsü yaratır.",
        "tests/test_invoice.py",
        "from decimal import ROUND_UP, Decimal\n",
        "from decimal import Decimal\n",
        "passed",
        "pytest: 14 test geçti (tests/test_invoice.py)",
        2010,
    ),
]


def file_summaries(findings: list[Finding]) -> list[FileSummary]:
    """Build per-file summaries with severity counts from *findings*."""
    summaries = {path: FileSummary(path=path, line_count=n) for path, n in FILES}
    for finding in findings:
        counts = summaries[finding.file].counts
        setattr(counts, finding.severity, getattr(counts, finding.severity) + 1)
    return list(summaries.values())
